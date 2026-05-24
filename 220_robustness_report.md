# 鲁棒性与统计显著性检验

- 场景：Scenario 1 + Pathfinder 几何
- 扰动方式：边容量独立乘以 `U(0.95, 1.05)` 随机因子
- 重复次数：`30`
- 比较算法：`ACO`、`PaperImprovedAStar`、`OurSinglePath`
- 显著性方法：配对符号翻转置换检验（paired sign-flip permutation test）

## 各算法均值 ± 标准差

### 总疏散时间 (s)
- `ACO`: `361.93 ± 24.27`
- `PaperImprovedAStar`: `335.20 ± 50.25`
- `OurSinglePath`: `278.53 ± 0.51`

### 累计排队时间 (人·秒)
- `ACO`: `59294.37 ± 1614.20`
- `PaperImprovedAStar`: `62589.40 ± 1074.71`
- `OurSinglePath`: `51277.93 ± 984.03`

### 中度拥挤暴露 (density > 3)
- `ACO`: `19615.87 ± 877.90`
- `PaperImprovedAStar`: `21090.93 ± 904.33`
- `OurSinglePath`: `18834.87 ± 914.36`

### 重度拥挤暴露 (density > 5)
- `ACO`: `8409.97 ± 558.54`
- `PaperImprovedAStar`: `13012.33 ± 545.86`
- `OurSinglePath`: `11139.17 ± 993.41`

## 显著性结果

### OurSinglePath vs ACO
- `总疏散时间 (s)`: 均值差（Our - Baseline）=`-83.40`，95% CI=`[-92.53, -75.33]`，`p=0.0000`，Our 胜率=`100.0%`
- `累计排队时间 (人·秒)`: 均值差（Our - Baseline）=`-8016.43`，95% CI=`[-8638.44, -7428.19]`，`p=0.0000`，Our 胜率=`100.0%`
- `中度拥挤暴露 (density > 3)`: 均值差（Our - Baseline）=`-781.00`，95% CI=`[-1150.97, -441.33]`，`p=0.0001`，Our 胜率=`76.7%`
- `重度拥挤暴露 (density > 5)`: 均值差（Our - Baseline）=`2729.20`，95% CI=`[2325.67, 3138.07]`，`p=0.0000`，Our 胜率=`0.0%`

### OurSinglePath vs PaperImprovedAStar
- `总疏散时间 (s)`: 均值差（Our - Baseline）=`-56.67`，95% CI=`[-73.53, -39.67]`，`p=0.0000`，Our 胜率=`100.0%`
- `累计排队时间 (人·秒)`: 均值差（Our - Baseline）=`-11311.47`，95% CI=`[-11817.60, -10775.35]`，`p=0.0000`，Our 胜率=`100.0%`
- `中度拥挤暴露 (density > 3)`: 均值差（Our - Baseline）=`-2256.07`，95% CI=`[-2706.28, -1823.49]`，`p=0.0000`，Our 胜率=`100.0%`
- `重度拥挤暴露 (density > 5)`: 均值差（Our - Baseline）=`-1873.17`，95% CI=`[-2315.64, -1445.35]`，`p=0.0000`，Our 胜率=`100.0%`

## 输出文件

- [216_robustness_raw_samples.csv](C:/Users/帅美婷sweet baby/Desktop/network/216_robustness_raw_samples.csv)
- [217_robustness_summary.csv](C:/Users/帅美婷sweet baby/Desktop/network/217_robustness_summary.csv)
- [218_robustness_significance_tests.csv](C:/Users/帅美婷sweet baby/Desktop/network/218_robustness_significance_tests.csv)
- [219_robustness_boxplots.png](C:/Users/帅美婷sweet baby/Desktop/network/219_robustness_boxplots.png)
