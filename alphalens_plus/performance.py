import pandas as pd
from scipy import stats
import empyrical as ep
from . import utils


def cumulative_returns(returns):
    """
    计算简单日度收益率序列的累积收益率（起点默认1）

    - 相对于alphalens原函数无改变，但输入时一般returns.shift(1)，因为收益率都是远期收益率，因子都是当日收盘后计算得出当日收盘后的持仓组合。
      同时，这里暂时不内置移动，所有收益率的移动均在函数外输入时调整。

    :param returns: 包含日度因子收益率序列
    :type returns: pd.Series
    :return: 累积收益率序列
    :return type: pd.Series
    :return example:
        2015-01-05   1.001310
        2015-01-06   1.000805
        2015-01-07   1.001092
        2015-01-08   0.999200
    """

    return ep.cum_returns(returns, starting_value=1)


def cumulative_returns_plus(returns, start_date=None, end_date=None, starting_value=1, ret_col='1D', with_excess=True) -> pd.DataFrame:
    """给定组合收益率序列1D和基准收益率序列1D_benchmark计算超额收益率

    - 这里一定要单独拿一个函数来封装就是因为超额收益率不能是先相减再累乘，而是要先计算净值后再相减
    - 如果1D收益率是基于t+1的open至t+2的open计算的，那么日期需要向后移动一个交易日

    Parameters
    ----------
    returns : 日度收益率序列dataframe，包含至少1D和1D_benchmark两个序列
    ret_col : 列名，默认1D逐日收益率
    start_date : 起始日期，默认样本数据的起点。注意，这里的起始日期是因子计算日，并非实际交易日。
                 一般而言是在因子计算日当日收盘后计算，所以最早的买入也是在下一个交易日的开盘。
    end_date : 结束日期，默认所有数据
    starting_value : 起始净值，默认1
    with_excess : 是否计算超额收益率，默认True。这里超额收益率使用净值计算，即策略累积净值与基准累计净值的差。

    Returns
    -------
    cum_returns : 累积净值数据，含3列，分别为组合净值1D，基准净值1D_benchmark和超额收益1D_excess。

    P.S
    ---
    注意，此时返回的收益率已经做了shift处理，返回结果的当日的数据便是当日收盘后的净值。理论上来讲只要是因子投资，且在收盘或收盘后才
    计算出因子值的，无论是T的close到T+1的close，还是T+1的open到T+1的close，只要涉及净值计算，都要shift(1)，因为此时输入的收益率
    都是1D forward（1日远期收益率）。
    """
    import rqdatac
    if not start_date:
        start_date = returns.index.min()
    # forward_returns必须要向后推移一日，这样当日的净值数据才是真实的净值数据（即实际持仓获得净值的数据），这里输入的start_date准确来讲是因子计算日
    # 而当start_date不是交易日时，理论上第一次买入是在下一个交易日的开盘，所以这里因子的计算日期是start_date的上一个交易日
    if not rqdatac.is_trading_date(start_date):
        start_date = rqdatac.get_previous_trading_date(start_date)
    if not end_date:
        end_date = returns.index.max()
    # end_date的逻辑和start_date相同
    if not rqdatac.is_trading_date(end_date):
        end_date = rqdatac.get_previous_trading_date(end_date)

    # 更新索引：因为收益率是用的T+1的open到T+2的open的ROC，所以实际索引要向后推一日
    # 此时T日的收益率数据才是T日的open到T+1的open的ROC，对应的净值也就是当日收盘后的净值（假设T+1日的开盘价卖出持有资产）
    returns_p = returns.loc[start_date:end_date].copy(deep=True).shift(1)

    returns_p.iloc[0] = 0  # 保证起点都是1，即真实持仓的return从下一日开始

    cum_returns = ep.cum_returns(returns_p, starting_value=starting_value)
    if with_excess:
        cum_returns[f'{ret_col}_excess'] = cum_returns[ret_col] - cum_returns[f'{ret_col}_benchmark'] + starting_value
    return cum_returns


def factor_weights(factor_data,
                   demeaned=False,
                   group_adjust=False,
                   equal_weight=True):
    """
    根据因子值计算资产的权重，然后通过它们绝对值的总和进行分配（以实现总杠杆率为 1）。
    正的因子值将转化为正的资产权重，负的因子值则转化为负权重。

    Parameters
    ----------
    factor_data : pd.DataFrame - MultiIndex
        这是一个以日期（第一层级）和资产（第二层级）为索引的多重索引 DataFrame，
        它包含单个 alpha 因子的数值、每个时期的前瞻性回报、该因子值所在的分位数/区间，以及（可选的）资产所属的分组信息。
        - 详细解释可参见 utils.get_clean_factor_and_forward_returns
    demeaned : bool
        这种计算是否应该应用于多空投资组合？
        如果答案是肯定的，那么权重将通过减去因子值的平均值并除以其绝对值之和来计算（以实现总杠杆率为 1）。
        正权重的总和将等于负权重的总和（按绝对值计算）。
        默认：False，即默认不做多空策略，近做多头策略
    group_adjust : bool
        这种计算是否应该应用于一个组别中性的投资组合？
        如果是的话，需要计算出组别中性的权重：确保每个组的权重相等。
        若启用“去均值化”选项，那么对因子值的去均值化处理将在各个组别层面上进行。
    equal_weight : bool, optional
        如果这个选项为真，那么资产将被赋予等同的权重，而不是基于各自因子的权重。
        如果选择了去均值化，那么整个因子池将被划分为两个等大的群体：
        表现较好的资产将获得正权重，而表现较差的资产则获得负权重。
        默认：True，即选股平均持仓
    Returns
    -------
    returns : pd.Series
        Assets weighted by factor value.
    """

    def to_weights(group, _demeaned, _equal_weight):

        if _equal_weight:
            group = group.copy()

            if _demeaned:
                # top assets positive weights, bottom ones negative
                group = group - group.median()

            negative_mask = group < 0
            group[negative_mask] = -1.0
            positive_mask = group > 0
            group[positive_mask] = 1.0

            if _demeaned:
                # positive weights must equal negative weights
                if negative_mask.any():
                    group[negative_mask] /= negative_mask.sum()
                if positive_mask.any():
                    group[positive_mask] /= positive_mask.sum()

        elif _demeaned:
            group = group - group.mean()

        return group / group.abs().sum()

    grouper = [factor_data.index.get_level_values('date')]
    if group_adjust:
        grouper.append('group')

    weights = factor_data.groupby(grouper)['factor'].apply(
        to_weights, demeaned, equal_weight)

    if group_adjust:
        weights = weights.groupby(level='date').apply(
            to_weights, False, False)

    return weights.rename('weight')


def quantile_turnover(quantile_factor, quantile, period=1,
                      date_field='date', asset_field='order_book_id'):
    """
    计算组间持仓股的更替情况
    """
    quant_names = quantile_factor[quantile_factor == quantile]
    # 统计选定分组的唯一持仓股（转化为set格式，方便后续进行比较）
    quant_name_sets = quant_names.groupby(level=[date_field]).apply(
        lambda x: set(x.index.get_level_values(asset_field)))

    name_shifted = quant_name_sets.shift(period)

    new_names = (quant_name_sets - name_shifted).dropna()
    # 计算组内换手率，注意：这里计算的分母是新一天的持仓，即换手率=新的股票数量/新的持仓总数=1-相同的股票数量/新的持仓总数
    quant_turnover = new_names.apply(
        lambda x: len(x)) / quant_name_sets.apply(lambda x: len(x))
    quant_turnover.name = quantile
    return quant_turnover


def rank_turnover(rank_factor_data, rank, period=1, ascending=False):
    """
    计算基于排序的组间持仓股的更替情况
    """
    # 如果是升序排列，原值越小，序号越小；原值越大，序号越大，暂时不支持
    if ascending:
        raise ValueError("目前仅支持降序排列，请确认数据的排序按照降序执行")
        # rank = rank_factor_data
        # rk_names = rank_factor_data[rank_factor_data <= rank]
    # 降序排列，原值越小，序号越大
    else:
        rk_names = rank_factor_data[rank_factor_data <= rank]
    # 以下计算逻辑与 quantile_turnover 相同
    # 统计选定分组的唯一持仓股（转化为set格式，方便后续进行比较）
    rk_name_sets = rk_names.groupby(level=['date']).apply(
        lambda x: set(x.index.get_level_values('order_book_id')))

    name_shifted = rk_name_sets.shift(period)

    new_names = (rk_name_sets - name_shifted).dropna()
    """new_names
    date
    2023-10-10    {002608.XSHE, 600248.XSHG, 601598.XSHG, 600500...
    2023-10-11              {600956.XSHG, 000582.XSHE, 600350.XSHG}
    2023-10-12    {600517.XSHG, 603713.XSHG, 000878.XSHE, 601139..
    """

    # 计算组内换手率，注意：这里计算的分母是新一天的持仓，即换手率=新的股票数量/新的持仓总数=1-相同的股票数量/新的持仓总数
    rk_turnover = new_names.apply(
        lambda x: len(x)) / rk_name_sets.apply(lambda x: len(x))
    rk_turnover.name = rank
    return rk_turnover


def portfolio_turnover(weights, period=1):
    """给定持仓数据，计算单边换手率


    - 情景1：所有个股平均持仓，此时直接统计两次持仓不同的股票数量再相除即可
    - 情景2：个股持仓不平均，此时输入的不再是个股持仓0-1矩阵，而是个股持仓权重，要求每日加总为1

    :param weights: 持仓权重，通常为交易日连续数据
    :param period: 换手率计算周期，默认1。一般不会改变，因为如果交易周期大于1，但实际输入的weights是日频的，只是周期内权重均相等。
    """
    weights = pd.pivot(weights.reset_index(), index='date', columns='order_book_id', values='weight')
    # 权重检查，要求逐日加总为1（日间存在差异此处不考虑）
    total_weights = weights.sum(axis=1)
    assert (total_weights.min() - 1.0) < 0.000001
    assert (total_weights.max() - 1.0) < 0.000001

    # FIXMEd：目前的计算逻辑有点小问题，体现在换仓时净值变化时，单纯市值占比相减得到的换手率和实际基于金额计算的换手率有偏差。
    #  换手率=（卖出金额+买入金额）/（最新总资产价值）
    turnover_rate = (weights.fillna(0).diff(period).abs().sum(axis=1) / 2)
    turnover_rate.iloc[0] = 1
    turnover_rate.name = 'turnover_rate'
    return turnover_rate


def annual_turnover(daily_turnover_rate, natural_day=True):
    """给定日度换手率序列，计算年化换手率"""
    total_turnover_rate = daily_turnover_rate.sum()
    sdate = daily_turnover_rate.index.min()
    edate = daily_turnover_rate.index.max()
    return total_turnover_rate / utils.get_natural_years(sdate, edate)


def factor_information_coefficient(factor_data,
                                   group_adjust=False,
                                   by_group=False, by_pandas=True):
    """
    Computes the Spearman Rank Correlation based Information Coefficient (IC)
    between factor values and N period forward returns for each period in
    the factor index.

    Parameters
    ----------
    factor_data : pd.DataFrame - MultiIndex
        A MultiIndex DataFrame indexed by date (level 0) and asset (level 1),
        containing the values for a single alpha factor, forward returns for
        each period, the factor quantile/bin that factor value belongs to, and
        (optionally) the group the asset belongs to.
        - See full explanation in utils.get_clean_factor_and_forward_returns
    group_adjust : bool
        Demean forward returns by group before computing IC.
    by_group : bool
        If True, compute period wise IC separately for each group.
    by_pandas: bool
        If True, compute period wise IC using pandas.DataFrame.corr(method='spearman'); else using stats.spearmanr().
        The difference lies between whether treat NaN through ignore or NaN: pandas.corr will ignore the NaN values,
        while scipy.stats.spearmanr will return NaN if any NaN exists;

    Returns
    -------
    ic : pd.DataFrame
        Spearman Rank correlation between factor and
        provided forward returns.
    """

    def src_ic(group):
        f = group['factor']
        # TODO: add rank-ic options
        _forward_returns_columns = utils.get_forward_returns_columns(factor_data.columns)
        if by_pandas:
            _ic = group[_forward_returns_columns.tolist() + ['factor']].corr(method='spearman').loc['factor', _forward_returns_columns]
        else:
            _ic = group[_forward_returns_columns].apply(lambda x: stats.spearmanr(x, f)[0])
        return _ic

    factor_data = factor_data.copy()

    grouper = [factor_data.index.get_level_values('date')]

    if group_adjust:
        factor_data = utils.demean_forward_returns(factor_data, grouper + ['group'])
    if by_group:
        grouper.append('group')

    ic = factor_data.groupby(grouper).apply(src_ic)

    return ic


def mean_information_coefficient(factor_data,
                                 group_adjust=False,
                                 by_group=False,
                                 by_time=None):
    """
    Get the mean information coefficient of specified groups.
    Answers questions like:
    What is the mean IC for each month?
    What is the mean IC for each group for our whole timerange?
    What is the mean IC for each group, each week?

    Parameters
    ----------
    factor_data : pd.DataFrame - MultiIndex
        A MultiIndex DataFrame indexed by date (level 0) and asset (level 1),
        containing the values for a single alpha factor, forward returns for
        each period, the factor quantile/bin that factor value belongs to, and
        (optionally) the group the asset belongs to.
        - See full explanation in utils.get_clean_factor_and_forward_returns
    group_adjust : bool
        Demean forward returns by group before computing IC.
    by_group : bool
        If True, take the mean IC for each group.
    by_time : str (pd time_rule), optional
        Time window to use when taking mean IC.
        See http://pandas.pydata.org/pandas-docs/stable/timeseries.html
        for available options.

    Returns
    -------
    ic : pd.DataFrame
        Mean Spearman Rank correlation between factor and provided
        forward price movement windows.
    """

    ic = factor_information_coefficient(factor_data, group_adjust, by_group)

    grouper = []
    if by_time is not None:
        grouper.append(pd.Grouper(freq=by_time))
    if by_group:
        grouper.append('group')

    if len(grouper) == 0:
        ic = ic.mean()

    else:
        ic = (ic.reset_index().set_index('date').groupby(grouper).mean())

    return ic
