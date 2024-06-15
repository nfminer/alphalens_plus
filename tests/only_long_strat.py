"""
基于Alphalens框架的回测
"""
import pandas as pd
import jtalpha.utils as jtautils
import jtalpha.analyzer_v2 as jta
from mytools.analyzer_v3 import get_strategy_returns
from jtalpha.analyzer_v2 import calculate_annual_turnover_rate
from alphalens_plus.utils import get_benchmark_returns
from alphalens_plus.performance import cumulative_returns, factor_weights, portfolio_turnover


def get_factor_data_v3_N(start_date=None, end_date=None):
    # factor_name = 'v3_3_md_cbr'
    # df_factor = pd.read_parquet(r"E:\daily_mission\20240402\df_scor_test_2023_V3_3_models_catboost_result.parquet").set_index(['date', 'order_book_id']).sort_index()
    # df_factor['factor'] = df_factor['y_pred_daily']
    factor_name = 'v3_2'
    df_factor = pd.read_parquet(r"E:\daily_mission\20240425\df_test_2023_v3_2_result.parquet").set_index(['date', 'order_book_id']).sort_index()
    df_factor['factor'] = df_factor['y_pred']
    # factor_name = 'v3_3'
    # df_factor = pd.read_parquet(r"E:\daily_mission\20240425\df_test_2023_v3_3_result.parquet").set_index(['date', 'order_book_id']).sort_index()
    # df_factor['factor'] = df_factor['y_pred']

    df_factor.index.names = ['date', 'order_book_id']
    if start_date is not None:
        df_factor = df_factor.loc[start_date:]
    if end_date is not None:
        df_factor = df_factor.loc[:end_date]
    df_factor.name = factor_name
    return df_factor


if __name__ == '__main__':
    st_dt = '2023-01-01'
    # factor_data = get_factor_data_v3(st_dt)
    factor_data = get_factor_data_v3_N(st_dt)

    # 参数设置
    __params__ = {
        "side": 1, "period": 5,  # 持仓方向和调仓周期

        # 全指指增 params
        "mktcap": (3.5e9, 5e12),  # 市值区间，默认左闭右开
        "tnovr": (25e6, 2e12),  # 成交额区间，默认左闭右开
        'limited_turning_rate': 0.4,  # 0.4 0.6 1
        'limited_stocks_num': 200,  # 持仓数量限制 lmt_nm
        'benchmark': '000852.XSHG',
        'sample_range': "000985.XSHG",
        "rebalance": False,

        "price_label": "vwap",  # 交易价格，默认VWAP
        'fee_deducted': True,  # 是否扣除手续费 fee_T
        'commission_fee_ratio': 0.001,  # 双边换手费用（一般不修改）
        'globe_init_amt': 1e9,  # 初始投资金额（一般不修改）
        'limited_updown': True,  # 是否限制交易日涨跌停（一般不修改）
        'not_limited_up': True,  # 是否限制因子日涨跌停（一般不修改）
    }

    __plot_params__ = {
        "fontsize": 16, "fontcolor": "red", "fontalpha": 1,  # 字体参数设置
        "ha": "left", "va": "bottom",  # 策略结果信息位置：左下
        "legend": "upper left",  # 图例位置：左上，策略整体上涨："lower right"；策略整体下跌："lower left"；策略震荡：随意，一般不会用
        # "ha": "left", "va": "top",  # 策略结果信息位置：左上
        # "legend": "lower right",  # 图例位置：右下
    }

    # 是否打印策略信息
    export_strat_holdings = False
    export_strat_netvalue_tnovr = False

    # 注解：除了价格，其他所有和仓位相关的数据都需要shift(1)来对齐时间
    # ###########################
    # 主函数
    prices_data = jtautils.get_prices_by_factor_data(factor_data)
    full_sorted_factor_data = jtautils.get_full_sorted_factor_data(factor_data, shift=1)

    # 生成基础持仓矩阵和调仓日期序列
    period = __params__['period']
    portfolios_pivot, positions_change_dates = jta.get_daily_target_portfolios(factor_data, period=period, latest=False, shift=1)  # 因子值在T日计算,影响的是T+1的持仓,所以shift=1

    # 设置约束条件并生成约束矩阵
    mkt_cap_range = __params__['mktcap']
    tot_tnovr_range = __params__['tnovr']
    not_limited_up = __params__['not_limited_up']
    sample_range = __params__.get('sample_range', None)  # 选股范围，例如000300.XSHG等
    df_valid = jtautils.get_restricted_stocks_pivot(
        factor_data, market_cap_range=mkt_cap_range,
        total_turnover_range=tot_tnovr_range, not_limited_up=not_limited_up,
        sample_range=sample_range, shift=1,  # 获取到的约束是T日收盘时的约束值，真正影响交易是在T+1日,所以需要shift=1
    )
    portfolios_pivot_valid = portfolios_pivot[df_valid].dropna(axis=1, how='all')

    factor_data_in = (
        portfolios_pivot_valid.stack().rename('factor').reset_index()
        .sort_values(by=['date', 'factor'], ascending=(1, 0))
        .groupby(by=['date'], group_keys=False)
        .head(200)
    )

    s_rets = get_strategy_returns(factor_data_in, method='open-to-open')
    s_daily_balance_net = cumulative_returns(s_rets.shift(1))
    weights = factor_weights(factor_data_in.set_index(['date', 'order_book_id']), demeaned=False, equal_weight=True, group_adjust=False).rename('weight')
    s_daily_turning_rate = portfolio_turnover(weights)

