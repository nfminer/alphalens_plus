from alphalens_plus.utils import compute_forward_returns
from pandas import (
    Series,
    DataFrame,
    date_range,
    MultiIndex,
    Timedelta,
    Timestamp,
    concat,
    read_parquet
)


dr = date_range(start='2015-1-1', end='2015-1-3')
mindex = MultiIndex.from_product([['A', 'B'], dr], names=['inst_id', 'date'])
prices = DataFrame(index=mindex, columns=['close', 'open'],
                   data=[[1, 1], [1, 2], [2, 1], [3, 1], [4, 2], [2, 1]])
prices = read_parquet(r'D:\msliu\projects\temp\prices_copy.parquet').set_index(['order_book_id', 'date'])
prices.index.names = ['inst_id', 'date']

fp = compute_forward_returns(prices, periods=[1, 2], on_open=False, filter_zscore=20)
print(fp.isnull().sum())
print(fp.shape)
