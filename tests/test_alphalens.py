# from alphalens.utils import *
# from alphalens.performance import *
# from alphalens.plotting import *


# factor_data = pd.read_parquet('./data/test_factor_data.parquet').loc['2023-10-01':]
# quantile_factor = quantize_factor(factor_data, quantiles=10).rename('factor')
# q10_factor = quantile_factor[quantile_factor == 10]
# # factor_weights: 根据因子值计算权重，
# fw = factor_weights(factor_data)
# # fw.groupby(by=['date']).apply(lambda i: i.abs().sum())

# fw_q = factor_weights(q10_factor.to_frame(), demeaned=False)
# # fw_q = factor_weights(q10_factor.to_frame(), demeaned=False, equal_weight=True)
# # fw_q.head(3)
# # fw_q.groupby(by=['date']).sum()
