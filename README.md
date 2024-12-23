# AlphalensPlus: A better toolbox for factors' alpha analysis

基于[Quantopian](https://github.com/quantopian)的[Alphalens](https://github.com/quantopian/alphalens)开发的升级版因子分析工具箱。

## Logging

+ 20241223:
  + alphalens_plus中的plotting主要包含针对量化投资的集成度较高的绘图工具，可以结合[mplfinance]这个模组进行更新和加强，
    而这也是放在alphalens_plus的原因，因为alphalens_plus的导出结果一般都是returns和weights等，
    同时需要与行情数据结合查看，所以放在一起（同时还绑定empyrical）。
  + 而其他类似dash、plotly、bokech则由于更偏向可视化，所以是单独模组负责，更多是属于alphalens的下游模组（接收alphalens的输出）。

## References

+ [quantopian/alphalens](https://github.com/quantopian/alphalens):
  + 原生alphalens项目，主体内容于2015年左右实现，目前可复用，但局部代码需更新。
  + 整体用作思路参考。

+ [stefan-jansen/alphalens-reloaded](https://github.com/stefan-jansen/alphalens-reloaded)
  + 大佬Stefan Jansen维护的alphalens项目，对最新版本python进行适配，可复用程度较高。
  + 是主要学习和参考的项目。

+ [github:vnpy_alphalens](https://github.com/vnpy/vnpy_alphalens)
  + vnpy的自适应版，更多面向回测系统使用，次要学习和参考项目。
