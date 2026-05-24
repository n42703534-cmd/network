# 第12页：空间瓶颈定位验证

数据来源：
- 左侧表格整理自 [203c_scenario1_pathfinder_spatial_bottlenecks.csv](/C:/Users/帅美婷sweet%20baby/Desktop/network/203c_scenario1_pathfinder_spatial_bottlenecks.csv)
- 结果脚本为 [scenario1_pathfinder_validation.py](/C:/Users/帅美婷sweet%20baby/Desktop/network/scenario1_pathfinder_validation.py)

检查结果：
- 拥堵节点已经跑出来了。
- `OurSinglePath` 下，你指定的 6 个重点节点全部命中。
- 这一页建议只讲“空间定位一致性”，不要讲 `5-17s` 这一列时间窗。
- 原因：`5-17s` 是模型里“节点核心区密度持续高于 3 p/m²”的高阈值窗口，不等于 Pathfinder 云图里肉眼看到的持续拥堵时长。

**页面标题**
空间瓶颈定位验证

**左侧放表**
建议标题：`OurSinglePath 识别的关键空间瓶颈节点`

| 排名 | 节点 | 类型 | 累计排队时间 (person-s) | 峰值人数 | 峰值密度 (p/m²) |
| --- | --- | --- | ---: | ---: | ---: |
| 2 | Gate_L7_West_Vert | gate | 3301.0 | 67 | 8.375 |
| 4 | Gate_L2_S_West | gate | 1856.0 | 129 | 9.214 |
| 5 | Gate_L18_E1 | gate | 1736.0 | 60 | 5.000 |
| 6 | Gate_L2_N_West | gate | 1368.0 | 74 | 9.250 |
| 7 | Gate_L2_S_East | gate | 1352.0 | 92 | 9.200 |
| 8 | Gate_L2_N_East | gate | 890.0 | 55 | 9.167 |

表下注释：
- 表中节点均来自 `OurSinglePath` 的空间瓶颈统计结果。
- 所有节点均可在 Pathfinder 二维密度云图中直接定位。
- 本页不展示 `first_over3_time_s / last_over3_time_s`，避免和 Pathfinder 可视拥堵时长混淆。

**右侧放图**
建议标题：`Pathfinder 密度云图验证`

建议放法：
- 放 1 张总览图，框出 `Gate_L7_West_Vert`、`Gate_L18_E1` 和 L2 四个闸机节点群。
- 如果版面允许，改成 2 张局部放大图更好：
  1. `Gate_L7_West_Vert` 附近高密度聚集截图
  2. `Gate_L18_E1` 或 `Gate_L2_S_West / Gate_L2_N_West` 附近高密度聚集截图

右图标注建议：
- 用红色或橙色框出高密度聚集区
- 用箭头标出节点名称
- 可加短标签：`High-density accumulation`

**这一页讲什么**
可直接念下面这段：

> 为验证算法识别出的关键空间瓶颈是否具有物理可解释性，我们将 `OurSinglePath` 输出的高拥堵节点，与 Pathfinder 密度云图中的高密度聚集区域进行对照。结果可以看到，`Gate_L7_West_Vert`、`Gate_L18_E1` 以及 L2 层的 `Gate_L2_S_West`、`Gate_L2_N_West`、`Gate_L2_S_East`、`Gate_L2_N_East` 等节点，均对应明显的人群聚集现象。说明模型不仅能够给出路径层面的优化结果，也能够较准确地定位真实疏散过程中的关键物理瓶颈位置。

**页内短句版**
- 算法识别出的关键物理瓶颈，在 Pathfinder 密度云图中均能观察到明显高密度聚集。
- 重点拥堵节点主要集中在 L7 竖向闸机、L18 出口闸机以及 L2 闸机群区域。
- 结果表明，模型对拥堵空间位置的识别具有较强现实一致性。

**这一页结论**
可直接放页尾：

> 空间定位具有较好一致性。

加强一点的版本：

> 算法识别的关键拥堵节点与 Pathfinder 高密度聚集区域高度对应，说明空间瓶颈定位具有较好一致性。

**补充说明**
- 如果后面你要做“时间一致性验证”，建议单独做一页，不要沿用 `203c` 里的 `5-17s` 这种高阈值节点窗口。
- 工作区里没有找到你提到的 `320_our_single_path_pathfinder_bottleneck_validation.md`，所以这份成稿是基于当前 `203c` 结果直接整理的。
