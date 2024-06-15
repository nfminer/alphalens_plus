"""
最优换手率/持仓周期研究
"""
import os
import numpy as np
import pandas as pd
from datetime import datetime, date
import jtalpha.analyzer_v2 as jta
import jtalpha.consts as jtac
import jtalpha.utils as jtautils  # 引用了本地的rqdata和rqfactors
import mytools.plotting as myplot
from mytools.analyzer_v3 import get_strategy_returns, pre_check_factor_data
from jtalpha.analyzer_v2 import calculate_annual_turnover_rate
from alphalens_plus.performance import cumulative_returns, factor_weights, portfolio_turnover
from alphalens_plus.utils import get_benchmark_returns

import warnings

warnings.filterwarnings('ignore')

today = datetime.today().strftime("%Y%m%d%H%M%S")


def get_factor_data_v28_live2(start_date=None, end_date=None):
    factor_name = 'v2_8-live'
    _factor_data_2021 = (
        pd.read_parquet(r"E:\daily_mission\20240422\df_test_2021_v2_8_result.parquet")
        [['date', 'order_book_id', 'y_pred', 'y_actual']]
        .rename(columns={'y_pred': 'factor'})
        .set_index(['date', 'order_book_id'])
        .sort_index()
        .loc[:'2021-12-31']
    )
    _factor_data_2022 = (
        pd.read_parquet(r"E:\daily_mission\20240419\df_test_2022_v2_8_result.parquet")
        [['date', 'order_book_id', 'y_pred', 'y_actual']]
        .rename(columns={'y_pred': 'factor'})
        .set_index(['date', 'order_book_id'])
        .sort_index()
        .loc[:'2022-12-31']
    )
    _factor_data_2023 = (
        pd.read_parquet(r"E:\daily_mission\20240412\df_test_20240410_v2_8_result.parquet")
        [['date', 'order_book_id', 'y_pred', 'y_actual']]
        .rename(columns={'y_pred': 'factor'})
        .set_index(['date', 'order_book_id'])
        .sort_index()
    )
    _factor_data = pd.concat([_factor_data_2021, _factor_data_2022, _factor_data_2023]).sort_index()
    if start_date is not None:
        _factor_data = _factor_data.loc[start_date:]
    if end_date is not None:
        _factor_data = _factor_data.loc[:end_date]
    _factor_data.name = factor_name
    return _factor_data


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
    # 1年数据
    st_dt = '2023-01-01'
    st_dts = [
        '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06', '2023-01-09',
        '2023-01-10', '2023-01-11', '2023-01-12', '2023-01-13', '2023-01-16',
        '2023-01-17',
    ]
    factor_data_all = get_factor_data_v3_N(st_dt)
    # 3年数据
    # st_dt = '2021-01-01'  # '2022-01-01'
    # st_dts = [
    #     '2021-01-05', '2021-01-06', '2021-01-07', '2021-01-08', '2021-01-11',
    #     '2021-01-12', '2021-01-13', '2021-01-14', '2021-01-15', '2021-01-18',
    #     '2021-01-19',
    # ]
    # factor_data_all = get_factor_data_v28_live2(st_dt)

    factor_name = factor_data_all.name
    factor_data_all = pre_check_factor_data(factor_data_all, method='close-to-close')

    sub_folder = 'long_out_opt_alphalens'

    # 参数设置
    __params__ = {
        "side": 1, "period": 1,  # 持仓方向和调仓周期
        # 全指指增 params
        "mktcap": (3.5e9, 5e12),  # 市值区间，默认左闭右开
        "tnovr": (25e6, 2e12),  # 成交额区间，默认左闭右开
        'limited_turning_rate': None,  # 0.4 0.6 1
        'limited_stocks_num': 200,  # 持仓数量限制 lmt_nm
        'benchmark': '000852.XSHG',
        'sample_range': "000985.XSHG",
        "rebalance": False,

        "price_label": "vwap",  # 交易价格，默认VWAP
        'fee_deducted': False,  # 是否扣除手续费 fee_T
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

    # 设置约束条件并生成约束矩阵
    mkt_cap_range = __params__['mktcap']
    tot_tnovr_range = __params__['tnovr']
    not_limited_up = __params__['not_limited_up']
    sample_range = __params__.get('sample_range', None)  # 选股范围，例如000300.XSHG等
    df_valid = jtautils.get_restricted_stocks_pivot(
        factor_data_all, market_cap_range=mkt_cap_range,
        total_turnover_range=tot_tnovr_range, not_limited_up=not_limited_up,
        sample_range=sample_range, shift=1,  # 获取到的约束是T日收盘时的约束值，真正影响交易是在T+1日,所以需要shift=1
    )

    # 生成基础持仓矩阵和调仓日期序列
    period = 1
    __params__['period'] = period

    for st_dt in st_dts[: period]:
        factor_data = factor_data_all.loc[st_dt:]
        portfolios_pivot, positions_change_dates = jta.get_daily_target_portfolios(factor_data, period=period, latest=False, shift=1)  # 因子值在T日计算,影响的是T+1的持仓,所以shift=1
        portfolios_pivot_valid = portfolios_pivot[df_valid].dropna(axis=1, how='all')

        factor_data_in = (
            portfolios_pivot_valid.stack().rename('factor').reset_index()
            .sort_values(by=['date', 'factor'], ascending=(1, 0))
            .groupby(by=['date'], group_keys=False)
            .head(200)
            .set_index(['date', 'order_book_id'])
        )
        factor_data_in['1D'] = factor_data_all['1D']

        s_rets = get_strategy_returns(factor_data_in)
        s_daily_balance_net = cumulative_returns(s_rets.shift(1))

        weights = factor_weights(factor_data_in, demeaned=False, equal_weight=True, group_adjust=False).rename('weight')
        s_daily_turning_rate = portfolio_turnover(weights)
        annual_turnover_rate = calculate_annual_turnover_rate(s_daily_turning_rate)

        # 将参数以字符的形式输出
        __params__toprint = __params__.copy()
        __not_printed_params = jtac.DEFAULT_NOT_PRINTED_PARAMS  # 不打印的内容（多为默认参数，详情参考jtalpha.consts）
        __params__toprint = jtautils.remove_params(__params__toprint, __not_printed_params)  # 删除不需要打印的参数
        __params__str = jtautils.format_params(__params__toprint)  # 格式化参数输出，分多行输出，文件名则一行输出且删除无效字符（换行符、空格、冒号等）
        __params__str_fileid = jtautils.rename_params(__params__str)  # 精简参数名称（20240314: 参数缩写调整在jtalpha.utils.rename_params中进行，主函数内一般不用修改）

        side = __params__['side']
        # 绘制策略详细结果图
        myplot.plot_cumulative_returns_amount(
            s_daily_balance_net,
            side=side, params_str=__params__str, annual_turnover_rate=annual_turnover_rate,
            benchmark=__params__.get('benchmark', '000852.XSHG'),
            img_path=f'{sub_folder}/{factor_name}_{__params__str_fileid}_{today}_{st_dt}.png',
            **__plot_params__,
        )

        fp_net_tnovr = f'{sub_folder}/{factor_name}_{__params__str_fileid}_{today}_{st_dt}_net_tnovr.parquet'
        df_net_tnovr = pd.concat([s_daily_turning_rate, s_daily_balance_net], axis=1)
        df_net_tnovr.columns = ['turning_rate', 'netvalue']
        df_net_tnovr.to_parquet(fp_net_tnovr)
        print("Finish", st_dt, period)

    for period in [2, 3, 4, 5, 6, 7, 8, 9, 10]:
        __params__['period'] = period
        for st_dt in st_dts[: period]:
            factor_data = factor_data_all.loc[st_dt:]
            portfolios_pivot, positions_change_dates = jta.get_daily_target_portfolios(factor_data, period=period, latest=False, shift=1)  # 因子值在T日计算,影响的是T+1的持仓,所以shift=1
            portfolios_pivot_valid = portfolios_pivot[df_valid].dropna(axis=1, how='all')

            factor_data_in = (
                portfolios_pivot_valid.stack().rename('factor').reset_index()
                .sort_values(by=['date', 'factor'], ascending=(1, 0))
                .groupby(by=['date'], group_keys=False)
                .head(200)
                .set_index(['date', 'order_book_id'])
            )
            factor_data_in['1D'] = factor_data_all['1D']

            s_rets = get_strategy_returns(factor_data_in, method='close-to-close')
            s_daily_balance_net = cumulative_returns(s_rets.shift(1))

            weights = factor_weights(factor_data_in, demeaned=False, equal_weight=True, group_adjust=False).rename('weight')
            s_daily_turning_rate = portfolio_turnover(weights)
            annual_turnover_rate = calculate_annual_turnover_rate(s_daily_turning_rate)

            # 将参数以字符的形式输出
            __params__toprint = __params__.copy()
            __not_printed_params = jtac.DEFAULT_NOT_PRINTED_PARAMS  # 不打印的内容（多为默认参数，详情参考jtalpha.consts）
            __params__toprint = jtautils.remove_params(__params__toprint, __not_printed_params)  # 删除不需要打印的参数
            __params__str = jtautils.format_params(__params__toprint)  # 格式化参数输出，分多行输出，文件名则一行输出且删除无效字符（换行符、空格、冒号等）
            __params__str_fileid = jtautils.rename_params(__params__str)  # 精简参数名称（20240314: 参数缩写调整在jtalpha.utils.rename_params中进行，主函数内一般不用修改）

            # 绘制策略详细结果图
            myplot.plot_cumulative_returns_amount(
                s_daily_balance_net,
                side=side, params_str=__params__str, annual_turnover_rate=annual_turnover_rate,
                benchmark=__params__.get('benchmark', '000852.XSHG'),
                img_path=f'{sub_folder}/{factor_name}_{__params__str_fileid}_{today}_{st_dt}.png',
                **__plot_params__,
            )
            fp_net_tnovr = f'{sub_folder}/{factor_name}_{__params__str_fileid}_{today}_{st_dt}_net_tnovr.parquet'
            df_net_tnovr = pd.concat([s_daily_turning_rate, s_daily_balance_net], axis=1)
            df_net_tnovr.columns = ['turning_rate', 'netvalue']
            df_net_tnovr.to_parquet(fp_net_tnovr)
            print("Finish", st_dt, period)

    # analyze: running in console
    from jtalpha.analyzer_v2 import calculate_annual_turnover_rate
    from alphalens_plus.utils import get_benchmark_returns
    from alphalens_plus.performance import cumulative_returns
    start_date = "2021-01-04"
    end_date = "2024-04-03"

    benchmark_returns = get_benchmark_returns(start_date, end_date, benchmark_order_book_id="000852.XSHG", method='close-to-close')['1D']
    bm_cum_returns = cumulative_returns(benchmark_returns.shift(1)).rename('1D_benchmark')

    all_annual_excess = pd.Series()
    all_files = os.listdir(sub_folder)
    for period in range(1, 11):
        tgt_val_tnovr_files = [file for file in all_files if (f'prd_{period}_' in file) and (file.endswith('.parquet') and ('holdings' not in file))]
        list_nets = []
        list_tnovrs = []
        for file in tgt_val_tnovr_files:
            df_net_tnovr_p = pd.read_parquet(os.path.join(sub_folder, file))
            list_nets.append(df_net_tnovr_p['netvalue'].rename(f"netvalue_{period}"))
            list_tnovrs.append(df_net_tnovr_p['turning_rate'].rename(f"tnovr_{period}"))
        s_avg_netval = pd.concat(list_nets, axis=1).fillna(1).mean(axis=1)
        s_avg_tnovr = pd.concat(list_tnovrs, axis=1).fillna(0).mean(axis=1)

        s_avg_excess = (s_avg_netval - bm_cum_returns).dropna() + 1
        excess_annual_ret = jta.calculate_annual_return(s_avg_excess)
        all_annual_excess[str(period)] = excess_annual_ret
        print("Finish", period)
        side = __params__['side']
        __params__['period'] = period
        __params__toprint = __params__.copy()
        __not_printed_params = jtac.DEFAULT_NOT_PRINTED_PARAMS
        __params__toprint = jtautils.remove_params(__params__toprint, __not_printed_params)
        __params__str = jtautils.format_params(__params__toprint)
        __params__str_fileid = jtautils.rename_params(__params__str)

        annual_turnover_rate = calculate_annual_turnover_rate(s_avg_tnovr)

        # 绘制策略详细结果图
        myplot.plot_cumulative_returns_amount(
            s_avg_netval,
            side=side, params_str=__params__str, annual_turnover_rate=annual_turnover_rate,
            benchmark=__params__.get('benchmark', '000852.XSHG'),
            img_path=f'{sub_folder}/{factor_name}_{__params__str_fileid}_{today}_avg.png',
            **__plot_params__,
        )
