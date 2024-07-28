import empyrical as ep
import pandas as pd
import numpy as np
import jtalpha.stats as jts

# 定义日期和收益率
dates = pd.date_range(start='2023-01-01', periods=10)
# returns = np.array([0.01, 0.02, -0.005, 0.015, 0.01, -0.01, 0.005, 0.02, -0.015, 0.01])
returns = np.array([-0.005,  -0.01, 0.03, 0.02, 0.015, 0.01, -0.01, 0.005, 0.02, -0.015, 0.01])

# 创建带有日期索引的收益率序列
# returns_series = pd.Series(returns, index=dates)
returns_series = returns

# 计算累积收益率
cum_returns = ep.cum_returns(returns_series, starting_value=1)

print("日度收益率：")
print(returns_series)
print("\n累积收益率：")
print(cum_returns)

cdd = jts.current_drawdown(returns)
print("最近回撤")
print(cdd)
