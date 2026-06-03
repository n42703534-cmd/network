# 鲁棒性与统计显著性检验

- 场景：Scenario 1 + Pathfinder 几何
- 扰动方式：边容量独立乘以 `U(0.95, 1.05)` 随机因子
- 固定设施失效：无
- 重复次数：`30`
- 比较算法：`ACO`、`PaperImprovedAStar`、`AdaptiveSingleNextHop`
- 显著性方法：配对符号翻转置换检验（paired sign-flip permutation test）

## 各算法均值 ± 标准差

### 总疏散时间 (s)
- `ACO`: `459.57 ± 1.71`
- `PaperImprovedAStar`: `343.68 ± 12.28`
- `AdaptiveSingleNextHop`: `397.80 ± 55.26`

### 累计排队时间 (人·秒)
- `ACO`: `53617.47 ± 1123.59`
- `PaperImprovedAStar`: `49357.88 ± 634.75`
- `AdaptiveSingleNextHop`: `45342.52 ± 1067.64`

### 中度拥挤暴露 (density > 3)
- `ACO`: `31072.73 ± 1021.95`
- `PaperImprovedAStar`: `25937.35 ± 318.25`
- `AdaptiveSingleNextHop`: `25562.53 ± 993.30`

### 重度拥挤暴露 (density > 5)
- `ACO`: `24525.63 ± 1201.86`
- `PaperImprovedAStar`: `18169.65 ± 349.86`
- `AdaptiveSingleNextHop`: `17757.50 ± 1138.78`

## 显著性结果

### AdaptiveSingleNextHop vs ACO
- `总疏散时间 (s)`: 均值差（Our - Baseline）=`-61.77`，95% CI=`[-81.12, -42.68]`，`p=0.0000`，Our 胜率=`100.0%`
- `累计排队时间 (人·秒)`: 均值差（Our - Baseline）=`-8274.95`，95% CI=`[-8778.81, -7773.16]`，`p=0.0000`，Our 胜率=`100.0%`
- `中度拥挤暴露 (density > 3)`: 均值差（Our - Baseline）=`-5510.20`，95% CI=`[-5988.37, -5046.14]`，`p=0.0000`，Our 胜率=`100.0%`
- `重度拥挤暴露 (density > 5)`: 均值差（Our - Baseline）=`-6768.13`，95% CI=`[-7353.40, -6221.36]`，`p=0.0000`，Our 胜率=`100.0%`

### AdaptiveSingleNextHop vs PaperImprovedAStar
- `总疏散时间 (s)`: 均值差（Our - Baseline）=`54.12`，95% CI=`[34.32, 72.40]`，`p=0.0001`，Our 胜率=`26.7%`
- `累计排队时间 (人·秒)`: 均值差（Our - Baseline）=`-4015.37`，95% CI=`[-4369.92, -3672.80]`，`p=0.0000`，Our 胜率=`100.0%`
- `中度拥挤暴露 (density > 3)`: 均值差（Our - Baseline）=`-374.82`，95% CI=`[-721.09, -39.72]`，`p=0.0412`，Our 胜率=`63.3%`
- `重度拥挤暴露 (density > 5)`: 均值差（Our - Baseline）=`-412.15`，95% CI=`[-850.38, 11.03]`，`p=0.0748`，Our 胜率=`53.3%`

## 输出文件

- [216_robustness_raw_samples.csv](C:/Users/帅美婷sweet baby/Desktop/network/216_robustness_raw_samples.csv)
- [217_robustness_summary.csv](C:/Users/帅美婷sweet baby/Desktop/network/217_robustness_summary.csv)
- [218_robustness_significance_tests.csv](C:/Users/帅美婷sweet baby/Desktop/network/218_robustness_significance_tests.csv)
- [219_robustness_boxplots.png](C:/Users/帅美婷sweet baby/Desktop/network/219_robustness_boxplots.png)
