import pandas as pd
import numpy as np
import re
import warnings


def compute_forward_returns(
        prices, periods=(1,),
        method='open-to-open',
        drop_na=True, drop_na_by='1D',
        asset_field='order_book_id', time_field='date',
        filter_zscore=20,
):
    """计算给定因子数据中资产和对应日期的远期收益率

    :param prices: 价格数据
        - 不同于alphalens的单独基于close计算，这里因为涉及以次日开盘价作为base price，
        因此传入的必须是长面板（即以date和asset为index的多列数据）。目前必须传入close和open，后续有需要再添加。
        示例数据如下::
                            close  open
        inst_id date
        A       2015-01-01      1     1
                2015-01-02      1     2
                2015-01-03      2     1
        B       2015-01-01      3     1
                2015-01-02      4     2
                2015-01-03      2     1
    :type prices: pd.DataFrame
    :param periods: 将要计算的forward_returns的周期元组列表，默认(1,)
    :type periods: tuple
    :param method: 计算收益率的方法，默认：'open-to-open' (FROC_{t} = OPEN_{t+2} / OPEN_{t+1})；
        其他方法还有：
        - close-to-close: FROC_{t} = CLOSE_{t+1} / CLOSE_{t}，这里假设当日收盘前有限时间内得到并计算出因子进行选股和买入；
        - open-to-close: FORC_{t} = CLOSE_{t+1} / OPEN_{t+1}，也就是当日开盘买入，收盘卖出（假设可以执行T+0操作）；
        因为股票价格数据存在高低开的说法，所以基于当日close和次日open的计算结果会有略微不同。
    :type method: str
    :param drop_na: 是否去除空值，默认：True（即：去除1D远期收益率的空值，在method为open-to-open的情况下要求个股至少有两日的开盘数据）
    :type drop_na: bool
    :param drop_na_by: 去除空值的依据，默认：1D的远期收益率
    :type drop_na_by: str
    :param filter_zscore: 是否基于标准化去除极端值，默认不去除
    :type filter_zscore: int, float
    :param asset_field: 资产列名称，默认：order_book_id
    :type asset_field: str
    :param time_field: 时间列名称，默认：date
    :type time_field: str
    
    :return: forward_returns
    :return type: pd.DataFrame
    """
    # 验证：至少包含close和open两列数据
    for col in ['close', 'open']:
        assert col in prices.columns

    prices_copy = prices.sort_index()[['close', 'open']].reset_index()

    raw_values_dict = dict()
    col_names = list()

    for period in sorted(periods):
        # 因为米筐返回的行情数据即使停牌也会有数据（成交量为0），所以可以直接分组shift即可
        # 这里采用的是分组shift方法计算（因为传入的是长面板），与alphalens原函数有所不同
        def forward_returns(g, _period=1):
            _g = g.set_index(time_field)
            if method == 'open-to-close':
                # 以t+1日开盘价为基准，在t+1的开盘价买入，t+period的收盘价卖出，本质是next_trddt的涨跌幅
                # 2D_Forward就是+2的close相对于+1的open，所以open一直都是shift(-1)，close随period改变
                _f_ret = _g['close'].shift(-1 * _period) / _g['open'].shift(-1) - 1
            elif method == 'open-to-open':
                # 以t+1日开盘价为基准，在t+1日开盘价买入，t+1+period的开盘价卖出
                # T日的open-to-open的ROC是T+2日的open相对于T+1的open的ROC
                _f_ret = _g['open'].pct_change(_period).shift(-1 * _period - 1)
            elif method == 'close-to-close':
                # 以t日收盘价为基准，t日收盘价买入，t+N日收盘价卖出
                _f_ret = _g['close'].pct_change(_period).shift(-1 * _period)
            elif method == 'vwap-to-vwap':
                _f_ret = _g['vwap'].pct_change(_period).shift(-1 * period)
            else:
                raise ValueError("目前仅支持 'close-to-close', 'open-to-close', 'open-to-open' 三种计算方法，请重新输入method参数。")
            return _f_ret

        col_name = '{}D'.format(period)
        # FIXME: 这里groupby有时会返回dataframe，有时直接返回series，原因是？暂时无法解决，先增加判断处理
        f_ret = prices_copy.groupby(by=[asset_field]).apply(
            forward_returns, _period=period
        )
        if isinstance(f_ret, pd.DataFrame):
            f_ret = f_ret.unstack()

        # 20240112: 确保以 asset_field 为第一级，time_field 为第二级
        # if f_ret.index.names != [time_field, asset_field]:
        #     f_ret = f_ret.swaplevel(time_field, asset_field)
        if f_ret.index.names != [asset_field, time_field]:
            f_ret = f_ret.swaplevel(asset_field, time_field)

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
        raw_values_dict[col_name] = f_ret.sort_index()
        col_names.append(col_name)

    df = pd.DataFrame.from_dict(raw_values_dict)
    if drop_na:
        df.dropna(subset=drop_na_by, inplace=True)

    # 20240112: 超额收益率一律在本函数外计算，本函数内最多同时计算指数的远期收益率（将指数当作一个asset）
    # if with_excess:
    #     # 加入基准收益率数据
    #     benchmark = kwargs.get('benchmark', None)
    #     assert benchmark in df.index.get_level_values(1)
    #     df_benchmark = df[df.index.isin([benchmark], level=1)]
    #     df = df.reset_index().merge(df_benchmark, on=[time_field], how='left', suffixes=('', '_benchmark')).set_index([asset_field, time_field])
    #     for col_name in col_names:
    #         df['{}_excess'.format(col_name)] = df[col_name] - df['{}_benchmark'.format(col_name)]
    return df


def get_clean_factor_and_forward_returns(
        factor, prices,
        periods=(1, ), method='open-to-open',
        benchmark=None,
        drop_na=True, drop_na_by='1D',
        asset_field='order_book_id', time_field='date',
):
    """基于因子数据获取行情数据

    :param factor: 以date（level 0）和asset（level 1）为复合主键的因子数据.
        - 示例数据如下：
                                    factor
        date       order_book_id
        2023-10-09 000009.XSHE    0.937139
                   000012.XSHE    0.963749
                   000021.XSHE    0.867523
    :type factor: pd.DataFrame
    :param prices: 以date（level 0）和asset（level 1）为复合主键的价格数据，默认date的序列比factor的date多period个周期（除非均为最新交易日）
        - 这里不采用pivot的核心原因是有时候收益率的计算不仅仅基于close，也可能涉及open
        - 示例数据如下：

    :param periods: 将要计算的forward_returns的周期元组列表，默认(1,)
    :param method: 计算收益率的方法，默认：'open-to-open'
    :type periods: tuple
    # :param adjust_type: 价格行权方法，默认：'post'（米筐接口中后复权的意思）
    :param benchmark: str, default '000905.XSHG'。业绩比较基准，默认中证500
    :param drop_na: 是否去除空值，默认：True（即：去除1D远期收益率的空值，在method为open-to-open的情况下要求个股至少有两日的开盘数据）
    :type drop_na: bool
    :param drop_na_by: 去除空值的依据，默认：1D的远期收益率
    :type drop_na_by: str
    :param asset_field: 资产列名称，默认：order_book_id
    :type asset_field: str
    :param time_field: 时间列名称，默认：date
    :type time_field: str

    :return: 包含因子数据、远期收益率和同期业绩基准收益率的长面板数据
        - 示例：
    :return type: pd.DataFrame
    """
    # 计算forward_returns
    forward_returns = compute_forward_returns(
        prices, periods=periods, method=method,
        time_field=time_field, asset_field=asset_field,
    )
    # FIXMEd:
    # 原本这里factor和clean_forward_returns的index顺序不同，factor是time_field在前，clean_forward_returns是asset_field在前
    # 修改clean_forward_returns的index顺序
    # 20240112：有效点的排除在函数外做
    # clean_forward_returns = forward_returns[
    #     (~forward_returns.index.isin(idx_novol)) &
    #     (~forward_returns.index.isin(idx_st))
    # ].swaplevel(time_field, asset_field)
    clean_forward_returns = forward_returns.swaplevel(time_field, asset_field)
    factor_data = factor.merge(clean_forward_returns, on=[time_field, asset_field], how='inner').sort_index()
    if drop_na:
        factor_data.dropna(subset=drop_na_by)
    if benchmark is not None:
        bm_forward_returns = forward_returns.loc[benchmark]
        factor_data = factor_data.join(bm_forward_returns['1D'].rename(benchmark), on=['date'], how='left')
    return factor_data


def demean_forward_returns(factor_data, grouper=None):
    """
    Convert forward returns to returns relative to mean
    period wise all-universe or group returns.
    group-wise normalization incorporates the assumption of a
    group neutral portfolio constraint and thus allows the
    factor to be evaluated across groups.

    For example, if AAPL 5 period return is 0.1% and mean 5 period
    return for the Technology stocks in our universe was 0.5% in the
    same period, the group adjusted 5 period return for AAPL in this
    period is -0.4%.

    Parameters
    ----------
    factor_data : pd.DataFrame - MultiIndex
        Forward returns indexed by date and asset.
        Separate column for each forward return window.
    grouper : list
        If True, demean according to group.

    Returns
    -------
    adjusted_forward_returns : pd.DataFrame - MultiIndex
        DataFrame of the same format as the input, but with each
        security's returns normalized by group.
    """

    factor_data = factor_data.copy()

    if not grouper:
        grouper = factor_data.index.get_level_values('date')

    cols = get_forward_returns_columns(factor_data.columns)
    factor_data[cols] = factor_data.groupby(grouper)[cols] \
        .transform(lambda x: x - x.mean())

    return factor_data


def get_forward_returns_columns(columns, require_exact_day_multiple=False):
    """
    Utility that detects and returns the columns that are forward returns
    """

    # If exact day multiples are required in the forward return periods,
    # drop all other columns (e.g. drop 3D12h).
    if require_exact_day_multiple:
        # pattern = re.compile(r"^(\d+([D]))+$", re.IGNORECASE)
        # Add excess returns options
        pattern = re.compile(r"^(\d+([D]))+$", re.IGNORECASE)
        valid_columns = [(pattern.match(col) is not None) for col in columns]

        if sum(valid_columns) < len(valid_columns):
            warnings.warn(
                "Skipping return periods that aren't exact multiples"
                + " of days."
            )
    else:
        pattern = re.compile(r"^(\d+([Dhms]|ms|us|ns]))+$", re.IGNORECASE)
        valid_columns = [(pattern.match(col) is not None) for col in columns]

    return columns[valid_columns]


def rethrow(exception, additional_message):
    """
    Re-raise the last exception that was active in the current scope
    without losing the stacktrace but adding a message.
    This is hacky because it has to be compatible with both python 2/3
    """
    e = exception
    m = additional_message
    if not e.args:
        e.args = (m,)
    else:
        e.args = (e.args[0] + m,) + e.args[1:]
    raise e


def non_unique_bin_edges_error(func):
    """
    Give user a more informative error in case it is not possible
    to properly calculate quantiles on the input dataframe (factor)
    """
    message = """
    An error occurred while computing bins/quantiles on the input provided.
    This usually happens when the input contains too many identical
    values and they span more than one quantile. The quantiles are chosen
    to have the same number of records each, but the same value cannot span
    multiple quantiles. Possible workarounds are:
    1 - Decrease the number of quantiles
    2 - Specify a custom quantiles range, e.g. [0, .50, .75, 1.] to get unequal
        number of records per quantile
    3 - Use 'bins' option instead of 'quantiles', 'bins' chooses the
        buckets to be evenly spaced according to the values themselves, while
        'quantiles' forces the buckets to have the same number of records.
    4 - for factors with discrete values use the 'bins' option with custom
        ranges and create a range for each discrete value
    Please see utils.get_clean_factor_and_forward_returns documentation for
    full documentation of 'bins' and 'quantiles' options.
    """

    def dec(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            if 'Bin edges must be unique' in str(e):
                rethrow(e, message)
            raise

    return dec


@non_unique_bin_edges_error
def quantize_factor(factor_data,
                    quantiles=5,
                    bins=None,
                    by_group=False,
                    no_raise=False,
                    zero_aware=False):
    """基于因子值计算个股分组情况

    Parameters
    ----------
    factor_data : pd.DataFrame - MultiIndex
        A MultiIndex DataFrame indexed by date (level 0) and asset (level 1),
        containing the values for a single alpha factor, forward returns for
        each period, the factor quantile/bin that factor value belongs to, and
        (optionally) the group the asset belongs to.

        - See full explanation in utils.get_clean_factor_and_forward_returns

    quantiles : int or sequence[float]
        Number of equal-sized quantile buckets to use in factor bucketing.
        Alternately sequence of quantiles, allowing non-equal-sized buckets
        e.g. [0, .10, .5, .90, 1.] or [.05, .5, .95]
        Only one of 'quantiles' or 'bins' can be not-None
    bins : int or sequence[float]
        Number of equal-width (value-wise) bins to use in factor bucketing.
        Alternately sequence of bin edges allowing for non-uniform bin width
        e.g. [-4, -2, -0.5, 0, 10]
        Only one of 'quantiles' or 'bins' can be not-None
    by_group : bool, optional
        If True, compute quantile buckets separately for each group.
    no_raise: bool, optional
        If True, no exceptions are thrown and the values for which the
        exception would have been thrown are set to np.NaN
    zero_aware : bool, optional
        If True, compute quantile buckets separately for positive and negative
        signal values. This is useful if your signal is centered and zero is
        the separation between long and short signals, respectively.
    # 当edge重复并删除后，第q_max组一直有完整的数据（即实现分组迁移的功能）的功能在函数外实现

    Returns
    -------
    factor_quantile : pd.Series
        Factor quantiles indexed by date and asset.
    """
    if not ((quantiles is not None and bins is None) or
            (quantiles is None and bins is not None)):
        raise ValueError('Either quantiles or bins should be provided')

    if zero_aware and not (isinstance(quantiles, int)
                           or isinstance(bins, int)):
        msg = ("zero_aware should only be True when quantiles or bins is an"
               " integer")
        raise ValueError(msg)

    def quantile_calc(x, _quantiles, _bins, _zero_aware, _no_raise):
        try:
            if _quantiles is not None and _bins is None and not _zero_aware:
                return pd.qcut(x, _quantiles, labels=False) + 1
            elif _quantiles is not None and _bins is None and _zero_aware:
                pos_quantiles = pd.qcut(x[x >= 0], _quantiles // 2,
                                        labels=False) + _quantiles // 2 + 1
                neg_quantiles = pd.qcut(x[x < 0], _quantiles // 2,
                                        labels=False) + 1
                return pd.concat([pos_quantiles, neg_quantiles]).sort_index()
            elif _bins is not None and _quantiles is None and not _zero_aware:
                return pd.cut(x, _bins, labels=False) + 1
            elif _bins is not None and _quantiles is None and _zero_aware:
                pos_bins = pd.cut(x[x >= 0], _bins // 2,
                                  labels=False) + _bins // 2 + 1
                neg_bins = pd.cut(x[x < 0], _bins // 2,
                                  labels=False) + 1
                return pd.concat([pos_bins, neg_bins]).sort_index()
        except Exception as e:
            if _no_raise:
                return pd.Series(index=x.index)
            raise e

    grouper = [factor_data.index.get_level_values('date')]
    if by_group:
        grouper.append('group')

    factor_quantile = factor_data.groupby(grouper)['factor'] \
        .apply(quantile_calc, quantiles, bins, zero_aware, no_raise)
    factor_quantile.name = 'factor_quantile'

    return factor_quantile.dropna()


def rank_factor(factor_data, ascending=False):
    """为因子数据排序

    :param factor_data: 因字数据，以date和order_book_id为索引，至少包含factor列
    :type factor_data: pd.DataFrame

    :param ascending: 是否升序排列，默认False（倒序），亦即数值越大，序号越小
    :type ascending: bool

    :return: 排序的因子值，以factor_rank命名，索引与factor_data相同
    :return type: pd.Series
    """
    # 这里不用rank取相反数，修改ascending即可
    factor_rank = factor_data.groupby(by=['date'])['factor'].rank(ascending=ascending)
    factor_rank.name = 'factor_rank'
    return factor_rank


def get_benchmark_returns(
        start_date, end_date,
        benchmark_order_book_id='000905.XSHG',
        periods=(1, 5, 6),
        adjust_type='post', method='open-to-open',
):
    """获取指定区间内业绩基准的表现情况（远期收益率）"""

    # 来源1：米筐api
    # import rqdatac
    # rqdatac.init(13601611030, 123456)
    # end_trddt = rqdatac.get_next_trading_date(end_date, 2)
    # prices = rqdatac.get_price(benchmark_order_book_id, start_date, end_trddt, adjust_type=adjust_type)

    # 来源2：本地api
    import jtdata
    end_trddt = jtdata.get_next_trading_date(end_date, 2)
    prices = jtdata.get_price(benchmark_order_book_id, start_date, end_trddt, adjust_type=adjust_type, frequency='1d')
    forward_returns = compute_forward_returns(
        prices, periods=periods, method=method,
    ).reset_index(0, drop=True)  # 这里compute_forward_returns返回的是order_book_id为0索引，date为1索引
    return forward_returns


def get_natural_years(start_date: pd.Timestamp, end_date: pd.Timestamp):
    return (end_date - start_date).days / 365
