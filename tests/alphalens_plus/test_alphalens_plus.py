import traceback
import pandas as pd
from mytools import rqdata

from alphalens_plus import utils
from alphalens_plus import performance as perf
import unittest


class JTDataTester(unittest.TestCase):

    def setUp(self):

        self.factor_data = pd.read_parquet('../data/factor_data_v38.parquet').loc['2023-10-01':, ['factor']]
        """factor_data.head(3)
                                    factor
        date       order_book_id          
        2023-10-09 000009.XSHE    0.937139
                   000012.XSHE    0.963749
                   000021.XSHE    0.867523
        """
        self.prices = rqdata.get_prices(self.factor_data)
        """prices[['close', 'open', 'volume']].head(3)
                                     close      open        volume
        order_book_id date                                        
        000009.XSHE   2023-10-09  122.8107  123.8827  8.100661e+05
                      2023-10-10  124.9548  122.8107  1.561483e+06
                      2023-10-11  124.7165  124.9548  9.822553e+05
        """
        self.start_date = '2023-12-01'
        self.end_date = '2024-01-31'

    def test_utils_get_benchmark_returns(self):
        # 默认000905.XSHG, open-to-open, 所有收益率均为远期
        # 例如1D表示T+1的open到T+2open的百分比变动
        # 如果是从prices的角度计算的话，就是prices['open'].pct_change().shift(-1-1)（因为pct_change是T-1到T，shift(-1)是T到T+1，shift(-1-1)才是T+1到T+2
        df_bm_rets = utils.get_benchmark_returns(self.start_date, self.end_date)
        """
                          1D        5D        6D
        date                                    
        2023-12-01 -0.006373 -0.018781 -0.003224
        2023-12-04 -0.017033  0.003170  0.002558
        2023-12-05  0.004921  0.019930  0.015514
        """
        assert isinstance(df_bm_rets, pd.DataFrame)

    def test_utils_get_clean_factor_and_forward_returns(self):
        factor_data_full = utils.get_clean_factor_and_forward_returns(self.factor_data, self.prices)
        """factor_data_full.head(3)
                                    factor        1D  000905.XSHG
        date       order_book_id                                 
        2023-10-09 000009.XSHE    0.937139  0.017459    -0.004693
                   000012.XSHE    0.963749 -0.026738    -0.004693
                   000021.XSHE    0.867523  0.016375    -0.004693
        """
        # 验证远期收益率计算是否正确
        # import rqdatac
        # prices = rqdatac.get_price('000009.XSHE', '2023-10-09', '2023-10-13', adjust_type='post')

    def test_utils_quantize_factor(self):
        # 测试：分组函数功能
        quantile_factor = utils.quantize_factor(self.factor_data, quantiles=10).rename('factor')
        """quantile_factor.head(3)
        date        order_book_id
        2023-10-09  000009.XSHE       8
                    000012.XSHE      10
                    000021.XSHE       2
        Name: factor, dtype: int64
        """

    def test_perf_factor_weights(self):
        quantile_factor = utils.quantize_factor(self.factor_data, quantiles=10).rename('factor')
        # 测试：基于持仓股构成及其因子信息计算个股持有权重-所有股票池的范围基于因子值设置权重
        fw = perf.factor_weights(self.factor_data)
        # fw.groupby(by=['date']).apply(lambda i: i.abs().sum())

        # 测试：基于持仓股构成及其因子信息计算个股持有权重-选定并持有某一分组的个股
        q10_factor = quantile_factor[quantile_factor == 10]
        fw_q = perf.factor_weights(q10_factor.to_frame(), demeaned=False)
        """fw_q.head(3)
        date        order_book_id
        2023-10-09  000012.XSHE      0.006711
                    000027.XSHE      0.006711
                    000030.XSHE      0.006711
        Name: weight, dtype: float64
        """
        # fw_q = factor_weights(q10_factor.to_frame(), demeaned=False, equal_weight=True)
        # fw_q.head(3)
        # fw_q.groupby(by=['date']).sum()

        # 测试：子账户不同开仓时点的调仓日期序列获取
        # all_dates_list = rqdata.get_all_portfolio_change_dates_list('20231001', '20240104', period=5)

        # 测试：业绩基准日度收益率序列获取
        # returns_bm = utils.get_benchmark_returns('2022-04-01', '2024-01-04')

    def test_utils_rank_factor(self):
        # 测试：基于排序等数量分组
        ranked_factor = utils.rank_factor(self.factor_data)
        """ranked_factor.head(3)
        date        order_book_id
        2023-10-09  000009.XSHE       428.0
                    000012.XSHE        56.0
                    000021.XSHE      1195.0
        Name: factor_rank, dtype: float64
        """


if __name__ == '__main__':
    unittest.main()
