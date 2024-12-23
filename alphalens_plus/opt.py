import numpy as np
import pandas as pd
import sys

python_version = sys.winver

if python_version >= '3.9':
    import cvxpy as cp
else:
    raise ImportError("cvxpy only support python>=3.9!")


def cal_variance(weights, df_stock):
    if len(weights) != df_stock.shape[1]:
        raise Exception("The weights should be the same size as the stock list")

    weights = np.array(weights / np.sum(weights))  # Normalizing
    returns_daily = (np.log(df_stock / df_stock.shift(1))).iloc[1:, :]
    Sigma = returns_daily.cov() * 244
    Portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(Sigma, weights)))

    return Portfolio_vol


def min_variance(df_stock):
    stock_num = df_stock.shape[1]
    w_min = 1 / (np.power(stock_num, 1.5))
    w_max = 0.6

    returns_daily = (np.log(df_stock / df_stock.shift(1))).iloc[1:, :]
    Sigma = returns_daily.cov() * 244

    # Define the weight variable
    weights = cp.Variable(stock_num)

    # Define the objective function
    portfolio_variance = cp.quad_form(weights, Sigma)

    # Define the constraints
    constraints = [
        cp.sum(weights) == 1,
        weights >= w_min,
        weights <= w_max
    ]

    # Define and solve the problem
    problem = cp.Problem(cp.Minimize(portfolio_variance), constraints)
    problem.solve()

    # Get the optimized weights
    optim_weight = weights.value.round(4)

    return optim_weight


def calculate_gmv_weights_with_cvxpy(cov_matrix):
    """
    使用cvxpy计算全局最小方差组合的个股权重

    参数：
    cov_matrix (numpy.ndarray): 大小为NxN的方差协方差矩阵

    返回：
    numpy.ndarray: 全局最小方差组合的个股权重
    """
    # 股票数量
    num_assets = cov_matrix.shape[0]
    w_min = 1 / (np.power(num_assets, 1.5))
    w_max = 0.6

    # 定义优化变量（权重）
    weights = cp.Variable(num_assets)

    # 目标函数：投资组合的方差
    portfolio_variance = cp.quad_form(weights, cov_matrix)

    # 约束条件：权重之和为1，权重非负（无法做空）
    constraints = [
        cp.sum(weights) == 1,
        weights >= w_min,
        weights <= w_max
    ]

    # 定义优化问题
    problem = cp.Problem(cp.Minimize(portfolio_variance), constraints)

    # 求解优化问题
    problem.solve()

    # 返回最优权重
    return weights.value.round(5)
