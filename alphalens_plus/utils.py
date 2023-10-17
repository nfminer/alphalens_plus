import pandas as pd
import numpy as np
import rqdatac


rqdatac.init(13585836852,123456)


def compute_forward_returns(prices, 
                            periods=(1, 5, 10), 
                            on_open=True, 
                            dropna=True, 
                            with_excess=False, 
                            filter_zscore=20,
                            **kwargs):
    """
    Parameters
    ----------
    prices: pd.DataFrame - MultiIndex
        不同于alphalens的单独基于close计算，这里因为涉及以次日开盘价作为base price，
        因此传入的必须是长面板（即以date和asset为index的多列数据）。目前必须传入close和open，后续有需要再添加。
        ::
                            close  open
        inst_id date                   
        A       2015-01-01      1     1
                2015-01-02      1     2
                2015-01-03      2     1
        B       2015-01-01      3     1
                2015-01-02      4     2
                2015-01-03      2     1
    periods: list - 周期序列，将要计算的forward_returns的周期
    on_open: bool, default True - 是否基于次日开盘价计算ROC。
        因为股票价格数据存在高低开的说法，所以基于当日close和次日open的计算结果会有略微不同。
    dropna: bool, default True - 是否去除空值，默认去除1D的空值（即至少有两日数据）
    with_excess: bool, defalt False - 是否计算超额收益率，默认不计算，若需要计算，则添加参数benchmark指定基准资产
    filter_zscore: int or float, default None - 是否基于标准化去除极端值，默认不去除
    **kwargs: 其他可能用到的键值对参数。
    
    Returns
    -------
    forward_returns: pd.DataFrame - MultiIndex
    """
    for col in ['close', 'open']:
        assert col in prices.columns
    asset_field = kwargs.get('asset_field', 'inst_id')
    time_field = kwargs.get('time_field', 'date')

    prices_copy = prices.sort_index()[['close', 'open']].reset_index()

    raw_values_dict = dict()
    col_names = list()
    
    for period in sorted(periods):
        # 因为米筐返回的行情数据即使停牌也会有数据（成交量为0），所以可以直接分组shift即可
        # 这里采用的是分组shift方法计算（因为传入的是长面板），与alphalens原函数有所不同
        def forward_returns(g, period=1):
            _g = g.set_index(time_field)
            if on_open:
                # 如果以次日开盘价为基准，则1D Forward的return就是next_trddt的涨跌幅
                # 2D_Forward就是+2的close相对于+1的open，所以open一直都是shift(-1)，close随period改变
                f_ret = _g['close'].shift(-1 * period) / _g['open'].shift(-1)  - 1
            else:
                f_ret = _g['close'].pct_change(period).shift(-1 * period)
            return f_ret
        
        col_name = '{}D'.format(period)
        # FIXME: 这里groupby有时会返回dataframe，有时直接返回series，原因是？
        #  暂时无法解决，先增加判断处理
        f_ret = prices_copy.groupby(by=[asset_field]).apply(
            forward_returns, period=period
        )
        if isinstance(f_ret, pd.DataFrame):
            f_ret = f_ret.unstack()
        
        # 确保以 time_field为第一级，asset_field为第二级
        if f_ret.index.names != [time_field, asset_field]:
            f_ret = f_ret.swaplevel(time_field, asset_field)
        
        # FIXME: 在未解决上述groupby问题时先不在函数内进行收益率的标准化或归一化
        # if filter_zscore is not None:
        #     # series和dataframe之间的unstack转换会涉及行列的转换（即多次unstack后，原来的列会变为行，这在基于axis计算时需要注意）
        #     # 此处默认axis==0，所以必须保证f_ret是以asset为index，date为columns，这个可以通过前述groupby保证，因为groupby的结果一定是asset为index，date为columns
        #     # 即使返回的series，首次unstack后也是如此
        #     mask = abs(
        #         f_ret - f_ret.mean()
        #     ) > (filter_zscore * f_ret.std())
        #     f_ret[mask] = np.nan
        # f_ret = f_ret.unstack()
        raw_values_dict[col_name] = f_ret
        col_names.append(col_name)
    # print(f_ret)
    df = pd.DataFrame.from_dict(raw_values_dict)
    if dropna:
        subset = kwargs.get('subset', ['1D'])
        df.dropna(subset=subset, inplace=True)
    # print(df.index.get_level_values(1), '000905.XSHG' in df.index.get_level_values(1))
    if with_excess:
        benchmark = kwargs.get('benchmark', None)
        assert benchmark in df.index.get_level_values(1)
        df_benchmark = df[df.index.isin([benchmark], level=1)]
        df = df.reset_index().merge(df_benchmark, on=[time_field], how='left', suffixes=('', '_benchmark')).set_index([asset_field, time_field])
        for col_name in col_names:
            df['{}_excess'.format(col_name)] = df[col_name] - df['{}_benchmark'.format(col_name)]
    return df


def get_clean_factor_and_forward_returns(factor, 
                                         periods=(1, 5, 10, 20, 30, 60), 
                                         benchmark='000905.XSHG',
                                         asset_field='order_book_id', 
                                         **kwargs):
    """基于因子数据获取行情数据
    
    Parameters
    ----------
    factor: pd.DataFrame - MultiIndex
         以date（level 0）和asset（level 1）为复合主键的因子数据
    periods: tuple, default (1, 5, 10, 20, 30, 60)
         forwar_returns的计算周期
    benchmark: str, default '000905.XSHG'
         业绩比较基准，默认中证500
    asset_field: str, default 'order_book_id'
         资产字段名称，默认 'order_book_id'
    **kwargs: 其他可能用到的键值对参数
    """
    time_field = kwargs.get('time_field', 'date')  # 时间序列主键一般都以date命名
    
    inst_ids = factor.index.get_level_values(1).unique().tolist()  # 另一种请求方式是index.levels[0]，但是可能会有bug，所以先get_level获取
    start_date = factor.index.get_level_values(0).min()
    end_date = factor.index.get_level_values(0).max()
    max_days = max(periods)
    sample_start_date = start_date
    sample_end_date = rqdatac.get_next_trading_date(end_date, n=max_days)
    
    # prices和后续相关运算的数据都是以asset为level 0，date为level 1
    # 在prices内部进行运算时影响不大，但如果涉及到和factor的merge运算，必须指定merge的columns（merge时index也会算进columns中）
    prices = rqdatac.get_price(inst_ids + [benchmark], sample_start_date, sample_end_date)
    
    # 计算forward_returns
    on_open = kwargs.get('on_open', True)
    dropna = kwargs.get('dropna', True)
    with_excess = kwargs.get('with_excess', True)
    forward_returns = compute_forward_returns(
        prices, periods=periods, on_open=on_open, dropna=dropna,
        with_excess=with_excess, benchmark=benchmark, asset_field=asset_field,
    )
    
    # 剔除成交量为0的点
    idx_novol = prices.query('volume==0').index
    # 剔除其中个股为ST股的点
    idx_st = rqdatac.is_st_stock(
        inst_ids,
        sample_start_date,
        sample_end_date,
    ).replace(False, np.NaN).T.stack().index  # stack在堆叠时自动删除NaN值，所以将不需要的点转为np.NaN; T转置是为了保证index形状一致
    
    # FIXMEd: 原本这里factor和clean_forward_returns的index顺序不同，factor是time_field在前，clean_forward_returns是asset_field在前
    #         修改clean_forward_returns的index顺序
    clean_forward_returns = forward_returns[
        (~forward_returns.index.isin(idx_novol)) & 
        (~forward_returns.index.isin(idx_st))
    ].swaplevel(time_field, asset_field)
    
    factor_data = (
        factor.merge(clean_forward_returns, on=[time_field, asset_field], how='inner')
        .dropna(subset=['1D']).sort_index()
    )
    return factor_data



# 函数测试
# df_factor_demo = df_factor[
#     (df_factor['order_book_id'].isin(['000100.XSHE', '600118.XSHG'])) &
#     (df_factor['date'] > '2022-01-01')
# ].set_index(['date', 'order_book_id'])
# get_clean_factor_and_forward_returns(df_factor_demo, periods=(1, 5))
