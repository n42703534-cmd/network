# compare

这个文件夹只放一个干净入口，不复制大批代码。

运行：

```powershell
python main.py
```

程序会先选择场景：

- `mode1`: 常规突发
- `mode4`: 双向满载

再选择权重模式。算法始终固定为 `AdaptiveSingleNextHop`：

- `Pathfinder-compatible / time-oriented`: 降低拥堵、下游释放、出口压力等惩罚，使输出更接近 Pathfinder 静态最短路分配。
- `Balanced`: 保持当前权重，兼顾时间、排队和拥堵暴露。
- `Safety-oriented`: 提高拥堵和瓶颈惩罚，优先降低高密度暴露和出口集中。
- 全部运行

输出只生成 CSV，不生成图表：

- `summary_metrics.csv`: 疏散时间、平均旅行时间、排队、拥堵、速度、出口均衡指标。
- `exit_usage.csv`: 各出入口人数和占比。
- `line_metrics.csv`: 各线路清空、排队、拥堵指标。
- `top_bottlenecks.csv`: 主要排队/拥堵瓶颈节点。

结果文件会保存在：

```text
compare/outputs/运行时间/
```

也可以直接命令行指定：

```powershell
python main.py --scenario 1 --profile 2
python main.py --scenario 4 --profile all
python main.py --scenario all --profile all
```
