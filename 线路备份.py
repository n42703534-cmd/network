# ==============================================================================
# lines_config.py
# 纯数据配置文件：没有任何业务逻辑，只存放节点、边、标高等静态数据
# ==============================================================================

# ==============================================================================
# 模块 1：全局配置表 (STATION CONFIGURATION)
# ==============================================================================

STATION_LEVELS = {
    "L2": {"hall": 0.0, "platform": -5.12},
    "L7": {"hall": -5.03, "platform": -11.75},
    "L16": {"hall": 5.15, "platform": 12.53},
    "L18": {"hall": -16.97, "platform": -5.027},
    "Maglev": {"hall": 6.65, "platform": 10.4}
}

# 专门给 Excel 动态计算距离用的显式映射表
PLATFORM_VERTICAL_SPECS = {
    "L7": {
        "platform_node": "Platform_L7",
        "vertical_group": "L7_VERTICALS",
        "gate_group": "L7_GATES",
        "station_name": "龙阳路"
    },
    "L2": {
        "platform_node": "Platform_L2",
        "vertical_group": "L2_VERTICALS",
        "gate_group": "L2_GATES",
        "station_name": "龙阳路"
    },
    "L16": {
        "platform_node": "Platform_L16",
        "vertical_group": "L16_VERTICALS",
        "gate_group": "L16_GATES",
        "station_name": "龙阳路"
    },
    "L18": {
        "platform_node": "Platform_L18",
        "vertical_group": "L18_VERTICALS",
        "gate_group": "L18_GATES",
        "station_name": "龙阳路"
    },
    "Maglev": {
        "platform_node": "Platform_Maglev",
        "vertical_group": "Maglev_VERTICALS",
        "gate_group": "Maglev_GATES",
        "station_name": "龙阳路"
    }
}

# ==============================================================================
# 模块 2：节点数据仓库 (NODES DATA)
# ==============================================================================

NODES_DATA = {
    # ---------------------------------------------------------
    # [2.1] 站台基准节点 (Platforms)
    # ---------------------------------------------------------
    "Platform_L7": {"pos": (2630.2, 6243.4), "type": "platform", "area": 1349.0},
    "Platform_L2": {"pos": (0, 0), "type": "platform", "area": 1846.0},
    "Platform_L16": {"pos": (3961.1, -10217.8), "type": "platform", "area": 4216.0},
    "Platform_L18": {"pos": (-5608.0, -18517.0), "type": "platform", "area": 2676.0},
    "Platform_Maglev": {"pos": (4533.8, -4498.2), "type": "platform", "area": 6340.0},

    # ---------------------------------------------------------
    # [2.2] 站台至站厅垂直设施 (Verticals)
    # ---------------------------------------------------------
    "L7_VERTICALS": {
        "Stair_L7_1": ["stair", 2.28, "up", (803.1, 6883.1)],
        "Escalator_L7_up1": ["escalator", 0.93, "up", (971.5, 6651.5)],
        "Stair_L7_2": ["stair", 1.88, "up", (2808, 6771.1)],
        "Stair_L7_3": ["stair", 2.48, "up", (4462, 6869.9)],
        "Escalator_L7_down1": ["escalator", 0.93, "stop up", (4462, 7096.4)],
    },

    "L2_VERTICALS": {
        "Stair_L2_1": ["stair", 2.83, "up", (-4151.1, 98.9)],
        "Stair_L2_2": ["stair", 2.83, "up", (-4217.8, -140.2)],
        "Stair_L2_3": ["stair", 2.83, "up", (-1645.1, 255.7)],
        "Escalator_L2_up1": ["escalator", 1.05, "up", (-1625.4, 33.0)],
        "Escalator_L2_down1": ["escalator", 1.05, "stop up", (1554.9, 550.6)],
        "Stair_L2_4": ["stair", 2.83, " up", (1589.1, 338.0)],
        "Stair_L2_5": ["stair", 2.83, " up", (4081.9, 718.4)],
        "Stair_L2_6": ["stair", 2.83, " up", (4106.9, 471.3)],
    },

    "L16_VERTICALS": {
        "Stair_L16_1": ["stair", 1.7, "down", (1801.6, -9222.5)],
        "Escalator_L16_up1": ["escalator", 0.93, "stop down", (1808.3, -9415.8)],
        "Escalator_L16_down1": ["escalator", 0.93, "down", (5586.7, -9232.1)],
        "Escalator_L16_down2": ["escalator", 0.93, "down", (5593.9, -9406.4)],
        "Stair_L16_2": ["stair", 1.7, "down", (8167.0, -9235.7)],
        "Escalator_L16_up2": ["escalator", 0.93, "stop down", (8088.7, -9417.1)],
        "Escalator_L16_up3": ["escalator", 0.93, "stop down", (1814.7, -10996.3)],
        "Stair_L16_3": ["stair", 1.7, "down", (1814.7, -11163.4)],
        "Escalator_L16_down3": ["escalator", 0.93, "down", (5604.3, -10985.8)],
        "Escalator_L16_down4": ["escalator", 0.93, "down", (5607.9, -11170.7)],
        "Escalator_L16_up4": ["escalator", 0.93, "stop down", (8085.2, -10993.0)],
        "Stair_L16_4": ["stair", 1.7, "down", (8159.9, -11170.8)],
    },

    "L18_VERTICALS": {
        "Escalator_L18_down1": ["escalator", 1.03, "down", (-7271.7, -15529.9)],
        "Escalator_L18_up1": ["escalator", 1.03, "stop down", (-7442.0, -15589.1)],
        "Stair_L18_1": ["stair", 1.7, "down", (-7617.1, -15659.0)],
        "Escalator_L18_up2": ["escalator", 1.03, "down", (-7794.0, -15721.7)],

        "Escalator_L18_down2": ["escalator", 1.03, "down", (-6384.2, -18120.3)],
        "Escalator_L18_up3": ["escalator", 1.03, "stop down", (-6559.5, -18179.7)],

        "Escalator_L18_down3": ["escalator", 1.03, "down", (-5854.9, -20844.8)],
        "Escalator_L18_up4": ["escalator", 1.03, "stop down", (-5667.9, -20787.0)],
        "Escalator_L18_up5": ["escalator", 1.03, "stop down", (-5488.5, -20727.7)],

        "Escalator_L18_up6": ["escalator", 1.03, "stop down", (-4565.1, -23268.0)],
        "Stair_L18_2": ["stair", 2.3, "down", (-4769.3, -23346.2)],
        "Escalator_L18_down4": ["escalator", 1.03, "down", (-4991.2, -23427.2)],

        "Escalator_L18_up7": ["escalator", 1.03, "stop down", (-3268.6, -28110.4)],
        "Escalator_L18_up8": ["escalator", 1.03, "stop down", (-3092.6, -28046.5)],
        "Escalator_L18_up9": ["escalator", 1.03, "stop down", (-2930.9, -27986.4)],
    },

    "Maglev_VERTICALS": {
        "Escalator_Maglev_down1": ["escalator", 0.93, "down", (1379, -2834.2)],
        "Stair_Maglev_1": ["stair", 1.3, "down", (1657.1, -2988.6)],
        "Escalator_Maglev_down2": ["escalator", 0.93, "down", (7564.4, -2806.3)],
        "Stair_Maglev_2": ["stair", 1.3, "down", (7337.7, -2980.6)],
        "Stair_Maglev_3": ["stair", 1.3, "down", (1666.7, -6015.5)],
        "Escalator_Maglev_down3": ["escalator", 0.93, "down", (1446.5, -6171.8)],
        "Stair_Maglev_4": ["stair", 1.3, "down", (7350, -5992.3)],
        "Escalator_Maglev_down4": ["escalator", 0.93, "down", (7587.5, -6154.4)],
        "Stair_Maglev_5": ["stair", 1.3, "down", (1803.7, -4412.8)],
        "Escalator_Maglev_up1": ["escalator", 0.93, "stop down", (1516.0, -4576.9)],  # 进站
        "Stair_Maglev_6": ["stair", 1.3, "down", (7192.2, -4393.8)],
        "Escalator_Maglev_up2": ["escalator", 0.93, "stop down", (7477.1, -4562.4)],  # 停运666
    },

    # ---------------------------------------------------------
    # [2.3] 站厅出入闸机 (Gates)
    # ---------------------------------------------------------
    "L7_GATES": {
        "Gate_L7_N_West": ["gate_tripod", 3, "out", (1418.8, 7143.7)],
        "Gate_L7_N_Mid": ["gate_tripod", 3, "out", (3019.3, 7217.1)],
        "Gate_L7_N_East": ["gate_wide", 2, "out", (3424.7, 7238.6)],
        "Gate_L7_West_Vert": ["gate_wide", 4, "out", (128.8, 6073.2)],
    },

    "L2_GATES": {
        "Gate_L2_N_West": ["gate_wide", 4, "out", (-2208.2, 1302.5)],
        "Gate_L2_N_East": ["gate_wide", 3, "out", (5442.2, 2076.3)],
        "Gate_L2_S_West": ["gate_wide", 7, "out", (-443.5, -622.8)],
        "Gate_L2_S_East": ["gate_wide", 5, "out", (2828.5, -557.8)],
    },

    "L16_GATES": {
        "Gate_L16_N1": ["gate_wide", 3, "out", (3912.0, -8969.2)],  # 进站
        "Gate_L16_N2": ["gate_wide", 3, "out", (4181.8, -8979.1)],
        "Gate_L16_S1": ["gate_wide", 10, "out", (3338.5, -11278.9)],  # 进站
        "Gate_L16_S2": ["gate_wide", 12, "out", (7359.4, -11355.7)],
    },

    "L18_GATES": {
        "Gate_L18_E1": ["gate_wide", 6, "out", (-3504.1, -21391.4)],
        "Gate_L18_E2": ["gate_wide", 5, "out", (-3159.8, -22347.3)],  # 进站
        "Gate_L18_S1": ["gate_wide", 8, "out", (-3581.3, -24724.5)],
        "Gate_L18_S2": ["gate_wide", 7, "out", (-4892.4, -25188.6)],  # 进站
    },

    "Maglev_GATES": {
        "Gate_Maglev_W1": ["gate_wide", 5, "out", (2644.5, -3351.8)],
        "Gate_Maglev_W2": ["gate_wide", 5, "out", (2659.9, -4087.6)],  # 进站
        "Gate_Maglev_W3": ["gate_wide", 5, "out", (2675.3, -5646.3)],
        "Gate_Maglev_E1": ["gate_wide", 3, "out", (6354.9, -4473.3)],  # 进站
    },

    # ---------------------------------------------------------
    # [2.4] 单线虚拟节点及出站设施 (Virtuals & Exit Internal)
    # ---------------------------------------------------------
    "L7_VIRTUALS": {
        "VN_L7_Corner_1": ["virtual", 6.5, 42.77, (7534.9, -842.7), 6.58],
        "VN_L7_Corner_2": ["virtual", 2.4, 30, (5698, -425.5), 3.3],
    },

    "L2_VIRTUALS": {
        "VN_L2_Corner_1": ["virtual", 6.8, 51.68, (1443.1, 5498.6), 7.6],
    },

    "L18_VIRTUALS": {
        "VN_L18_Exit12_Entrance": ["virtual", 7.0, 44, (-3182.7, -20056.2)],
        "VN_L18_Exit17_Entrance": ["virtual", 6.5, 65, (-4172.4, -28261.4)],
        "VN_L18_Exit13_Entrance": ["virtual", 6.0, 60, (974.9, -36432.4)],
    },

    "L18_EXIT_VERTICALS": {
        "Stair_L18_Exit12": ["stair", 1.7, "up", (538.6, -17435.5)],
        "Escalator_L18_Exit12_up1": ["escalator", 1.03, "up", (195.7, -17106.0)],
        "Escalator_L18_Exit12_up2": ["escalator", 1.03, "up", (235.3, -17279.8)],
        "Stair_L18_Exit17": ["stair", 1.7, "up", (-6886.3, -28428.0)],
        "Escalator_L18_Exit17_up1": ["escalator", 1.03, "up", (-7189.4, -28702.7)],
        "Escalator_L18_Exit17_up2": ["escalator", 1.03, "up", (-7023.8, -28669.8)],
    },

    "Maglev_EXIT_VERTICALS": {
        "Stair_Maglev_Exit18": ["stair", 1.7, "down", (3129.2, -2990.5)],
        "Escalator_Maglev_Exit18": ["escalator", 0.93, "down", (3262.4, -2834.1)],
        "Stair_Maglev_Exit19": ["stair", 1.7, "down", (5864.2, -2989.9)],
        "Escalator_Maglev_Exit19": ["escalator", 0.93, "down", (5835.1, -2813.5)],
        "Stair_Maglev_Exit20": ["stair", 1.7, "down", (3138.9, -6007.9)],
        "Escalator_Maglev_Exit20": ["escalator", 0.93, "down", (3277.9, -6158.4)],
        "Stair_Maglev_Exit21": ["stair", 1.7, "down", (5872.4, -6003.9)],
        "Escalator_Maglev_Exit21": ["escalator", 0.93, "down", (5845.4, -6183.4)],
    },

    # ---------------------------------------------------------
    # [2.5] 最终地面出入口 (All Exits)
    # ---------------------------------------------------------
    "ALL_EXITS": {
        "Exit_L7_8/9": {"pos": (-891.6, 8776.9), "width": 6.5},
        "Exit_L7_7": {"pos": (-322.2, 5145.1), "width": 3.29},
        "Exit_L2_2": {"pos": (-2385.1, 2368.3), "width": 7.54},
        "Exit_L2_6": {"pos": (5247.8, 4759.4), "width": 5.2},
        "Exit_L2_4": {"pos": (-455.5, -1469.2), "width": 7.6},
        "Exit_L2_3": {"pos": (2904.3, -1231.7), "width": 4.2},

        "Exit_L16_10": {"pos": (6512.2, -8747.0), "width": 8.3},
        "Exit_L16_11": {"pos": (5178.2, -13258.1), "width": 34.6},

        "Exit_L18_12": {"pos": (-3182.7, -19800.0), "width": 7.0},
        "Exit_L18_13": {"pos": (2964.2, -35864.0), "width": 6.0},
        "Exit_L18_17": {"pos": (-4172.4, -28000.0), "width": 6.5},

        # 这里的 pos 坐标只为画图服务，绝对不影响你严谨的疏散时间计算！
        "Exit_Maglev_18": {"pos": (3300.0, -2800.0), "width": 10},
        "Exit_Maglev_19": {"pos": (6000.0, -2800.0), "width": 10},
        "Exit_Maglev_20": {"pos": (3300.0, -6200.0), "width": 10},
        "Exit_Maglev_21": {"pos": (6000.0, -6200.0), "width": 10},
    },

    # ---------------------------------------------------------
    # [2.6] 换乘通道及换乘虚拟节点 (Transfer Systems)
    # ---------------------------------------------------------
    "TRANSFER_VIRTUALS": {
        # 7换2 相关
        "VN_7to2_Entrance": ["virtual", 6.58, 44.55, (6239.9, 1643.5), 6.77],
        "VN_2to7_Exit": ["virtual", 6.58, 32.9, (6394.2, 5471.3), 5.0],
        "VN_L7toL2_Hall_Arrival": ["virtual", 10.0, 70, (787.8, -5610.9)],

        # 磁悬浮换2 相关
        "VN_Maglev_to_L2_Entrance": ["virtual", 13.0, 78, (8214.8, -2707.7)],
        "VN_Maglev_to_L2_Arrival": ["virtual", 14.0, 84, (6532.1, -267.7)],

        # 16换磁悬浮 相关
        "VN_L16_to_Maglev_Entrance": ["virtual", 13.0, 70, (9989.7, -8294.3)],
        "VN_L16_to_Maglev_Arrival": ["virtual", 13.0, 70, (8357.2, -6201.2)],

        # 2换16 相关
        "VN_L2_to_L16_Entrance": ["virtual", 10.0, 80, (-6317.8, -1120.4)],
        "VN_L2_to_L16_Passageway_Start": ["virtual", 13.5, 60, (-6851.7, -3135.7)],
        "VN_L2_to_L16_Passageway_End": ["virtual", 13.5, 80, (-6847.4, -6731.6)],
        "VN_L2_to_L16_Bridge_Trapezoid": ["virtual", 14.0, 380, (-5026.9, -8215.6)],
        "VN_L2_to_L16_Hall_Arrival": ["virtual", 18.0, 150, (-927.8, -9275.9)],

        # 18换16 / 16换18 (Y字型漏斗) 相关
        "VN_L2_to_L18_Transfer_Start": ["virtual", 15.0, 150, (-5471.3, -10088.3)],
        "VN_L16_to_L18_Transfer_Start": ["virtual", 15.0, 150, (750.4, -12199.0)],
        "VN_L18_Mid_Platform_A": ["virtual", 15.0, 200, (-5479.1, -12245.3)],
        "VN_L18_Mid_Platform_B": ["virtual", 15.0, 200, (-1992.4, -12896.0)],
        "VN_L18_Hall_Arrival_Base": ["virtual", 20.0, 250, (-4197.0, -16365.8)],
        "VN_L18_Hall_Split_A": ["virtual", 6.5, 80, (-4988.9, -17026.4)],
        "VN_L18_Hall_Split_B": ["virtual", 6.5, 80, (-4693.3, -17905.3)],
        "VN_L18_to_L16_Entrance": ["virtual", 15.0, 150, (-4241.7, -19158.1)],
        "VN_L18_to_L16_Split_A": ["virtual", 7.5, 60, (-3169.3, -18225.1)],
        "VN_L18_to_L16_Split_B": ["virtual", 7.5, 60, (-2873.5, -19022.1)],
        "VN_L18_to_L16_Merge": ["virtual", 15.0, 150, (-2061.7, -18289.5)],
        "VN_L18_to_L16_Mid_Platform_Start": ["virtual", 12.0, 200, (2639.0, -15741.5)],
        "VN_L18_to_L16_Mid_Platform_End": ["virtual", 12.0, 200, (5589.0, -15021.1)],
        "VN_L18_to_L16_Hall_Arrival": ["virtual", 11.0, 200, (9826.5, -12177.3)],
    },

    "TRANSFERS": {
        # 7换2 物理设施
        "Transfer_L7-L2_Z": ["passageway", 6.77, "up", (5846.5, 1690.3), 916.0],
        "Transfer_L7-L2_Stair": ["stair", 2.49, "up", (1929.3, -5711.8)],
        "Transfer_L7-L2_Esc1": ["escalator", 0.86, "up", (1908.6, -5937.9)],
        "Transfer_L7-L2_Esc2": ["escalator", 0.86, "up", (1949.1, -5483.9)],
        "Transfer_L2-L7_Passageway": ["passageway", 7.7, "down", (5520.7, 5522.1), 231],

        # 磁悬浮换2 物理设施
        "Transfer_Maglev_L2_Esc1": ["escalator", 1.03, "down", (7402.4, -2358.8)],
        "Transfer_Maglev_L2_Esc2": ["escalator", 1.03, "down", (7684.3, -2163.6)],
        "Transfer_Maglev_L2_Esc3": ["escalator", 1.03, "down", (7802.6, -2053.8)],
        "Transfer_Maglev_L2_Stair": ["stair", 2.0, "down", (7956.4, -1917.2)],

        # 16换磁悬浮 物理设施
        "Transfer_L16_Maglev_Passageway": ["passageway", 13, "one_way", (9030.3, -7260.3), 245],

        # 2换16 物理设施
        "Transfer_L2_L16_Esc1": ["escalator", 1.0, "up", (-5997.3, -1298.8)],
        "Transfer_L2_L16_Esc2": ["escalator", 1.0, "up", (-6173.7, -1281.6)],
        "Transfer_L2_L16_Esc3": ["escalator", 1.0, "up", (-6352.2, -1301.0)],
        "Transfer_L2_L16_Esc4": ["escalator", 1.0, "up", (-6528.5, -1285.9)],

        # 18换16 上行设施
        "Transfer_L18_L16_F1_Stair": ["stair", 1.7, "up", (-1811.4, -17743.8)],
        "Transfer_L18_L16_F1_Esc1": ["escalator", 1.03, "up", (-1695.5, -17855.9)],
        "Transfer_L18_L16_F1_Esc2": ["escalator", 1.03, "up", (-1579.5, -17967.8)],
        "Transfer_L18_L16_F1_Esc3": ["escalator", 1.03, "up", (-1463.7, -18079.8)],
        "Transfer_L18_L16_F1_Esc4": ["escalator", 1.03, "up", (-1347.8, -18191.9)],
        "Transfer_L18_L16_F2_Stair": ["stair", 1.7, "up", (9013.9, -12623.5)],
        "Transfer_L18_L16_F2_Esc1": ["escalator", 1.03, "up", (9153.8, -12488.2)],
        "Transfer_L18_L16_F2_Esc2": ["escalator", 1.03, "up", (9293.7, -12353.0)],
        "Transfer_L18_L16_F2_Esc3": ["escalator", 1.03, "up", (9433.6, -12217.7)],
        "Transfer_L18_L16_F2_Esc4": ["escalator", 1.03, "up", (9573.5, -12082.4)],

        # 换乘18 下行设施 (左路：2/7侧)
        "Transfer_L2_L18_F1_Esc1": ["escalator", 1.03, "down", (-5285.3, -10556.9)],
        "Transfer_L2_L18_F1_Esc2": ["escalator", 1.03, "down", (-5447.8, -10556.0)],
        "Transfer_L2_L18_F1_Esc3": ["escalator", 1.03, "down", (-5598.1, -10557.6)],
        "Transfer_L2_L18_F1_Stair": ["stair", 1.7, "down", (-5835.0, -10769.6)],

        # 换乘18 下行设施 (右路：16侧)
        "Transfer_L16_L18_F1_Esc1": ["escalator", 1.03, "down", (67.6, -12675.5)],
        "Transfer_L16_L18_F1_Esc2": ["escalator", 1.03, "down", (64.5, -12846.8)],
        "Transfer_L16_L18_F1_Stair": ["stair", 1.7, "down", (-80.6, -13024.7)],

        # 换乘18 共用下行设施 (分流汇入18号线站厅)
        "Transfer_Mid_L18_F2_Left_Esc1": ["escalator", 1.03, "down", (-4856.6, -13709.0)],
        "Transfer_Mid_L18_F2_Left_Esc2": ["escalator", 1.03, "down", (-5020.5, -13763.3)],
        "Transfer_Mid_L18_F2_Left_Esc3": ["escalator", 1.03, "down", (-5183.4, -13805.6)],
        "Transfer_Mid_L18_F2_Left_Esc4": ["escalator", 1.03, "down", (-5346.3, -13859.8)],
        "Transfer_Mid_L18_F2_Right_Esc1": ["escalator", 1.03, "down", (-4273.1, -13786.6)],
        "Transfer_Mid_L18_F2_Right_Esc2": ["escalator", 1.03, "down", (-4093.5, -13724.5)],
        "Transfer_Mid_L18_F2_Right_Stair": ["stair", 1.7, "down", (-3914.7, -13715.8)],
    }
}


# ==============================================================================
# 模块 3：单线边关系生成逻辑 (SINGLE LINE EDGES)
# ==============================================================================

def edge(u, v, length=None, width_limit=None, edge_type=""):
    return {"u": u, "v": v, "length": length, "width_limit": width_limit, "edge_type": edge_type}


# ---------------------------------------------------------
# [3.1] L7 线路边关系
# ---------------------------------------------------------
L7_VERTICAL_TO_GATE = [
    ("Stair_L7_1", "Gate_L7_N_West", None, 5.2),
    ("Escalator_L7_up1", "Gate_L7_N_West", None, 5.2),
    ("Stair_L7_2", "Gate_L7_N_West", None, 6.58),
    ("Stair_L7_3", "Gate_L7_N_West", None, 6.58),
    ("Escalator_L7_down1", "Gate_L7_N_West", None, 6.58),
    ("Stair_L7_1", "Gate_L7_N_Mid", None, 6.58),
    ("Escalator_L7_up1", "Gate_L7_N_Mid", None, 6.58),
    ("Stair_L7_2", "Gate_L7_N_Mid", None, 5.2),
    ("Stair_L7_3", "Gate_L7_N_Mid", None, 5.2),
    ("Escalator_L7_down1", "Gate_L7_N_Mid", None, 5.2),
    ("Stair_L7_1", "Gate_L7_N_East", None, 6.58),
    ("Escalator_L7_up1", "Gate_L7_N_East", None, 6.58),
    ("Stair_L7_2", "Gate_L7_N_East", None, 5.2),
    ("Stair_L7_3", "Gate_L7_N_East", None, 5.2),
    ("Escalator_L7_down1", "Gate_L7_N_East", None, 5.2),
    ("Stair_L7_1", "Gate_L7_West_Vert", None, 6.58),
    ("Escalator_L7_up1", "Gate_L7_West_Vert", None, 6.58),
    ("Stair_L7_2", "Gate_L7_West_Vert", None, 6.58),
    ("Stair_L7_3", "Gate_L7_West_Vert", None, 6.58),
    ("Escalator_L7_down1", "Gate_L7_West_Vert", None, 6.58),
]

L7_GATE_TO_VIRTUAL = [
    ("Gate_L7_N_West", "VN_L7_Corner_1", None, 6.5),
    ("Gate_L7_N_Mid", "VN_L7_Corner_1", None, 6.5),
    ("Gate_L7_N_East", "VN_L7_Corner_1", None, 6.5),
    ("Gate_L7_West_Vert", "VN_L7_Corner_1", None, 11.1),
    ("Gate_L7_N_West", "VN_L7_Corner_2", None, 8.0),
    ("Gate_L7_N_Mid", "VN_L7_Corner_2", None, 8.0),
    ("Gate_L7_N_East", "VN_L7_Corner_2", None, 8.0),
    ("Gate_L7_West_Vert", "VN_L7_Corner_2", None, 6.0),
]

L7_VIRTUAL_TO_EXIT = [
    ("VN_L7_Corner_1", "Exit_L7_8/9", None, 6.5),
    ("VN_L7_Corner_2", "Exit_L7_7", None, 2.3),
]

# ---------------------------------------------------------
# [3.2] L2 线路边关系
# ---------------------------------------------------------
L2_VERTICAL_TO_GATE = [
    ("Stair_L2_1", "Gate_L2_N_West", None, 7.0),
    ("Stair_L2_1", "Gate_L2_N_East", None, 7.0),
    ("Stair_L2_1", "Gate_L2_S_West", None, 7.5),
    ("Stair_L2_1", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_up1", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_up1", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_up1", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_up1", "Gate_L2_S_East", None, 7.5),
    ("Stair_L2_2", "Gate_L2_N_West", None, 7.0),
    ("Stair_L2_2", "Gate_L2_N_East", None, 7.0),
    ("Stair_L2_2", "Gate_L2_S_West", None, 7.5),
    ("Stair_L2_2", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_up2", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_up2", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_up2", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_up2", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_down1", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_down1", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_down1", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_down1", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_down2", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_down2", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_down2", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_down2", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_up3", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_up3", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_up3", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_up3", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_down3", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_down3", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_down3", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_down3", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_up4", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_up4", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_up4", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_up4", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_up5", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_up5", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_up5", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_up5", "Gate_L2_S_East", None, 7.5),
    ("Escalator_L2_up6", "Gate_L2_N_West", None, 7.0),
    ("Escalator_L2_up6", "Gate_L2_N_East", None, 7.0),
    ("Escalator_L2_up6", "Gate_L2_S_West", None, 7.5),
    ("Escalator_L2_up6", "Gate_L2_S_East", None, 7.5),
    ("Stair_L2_3", "Gate_L2_N_West", None, 7.0),
    ("Stair_L2_3", "Gate_L2_N_East", None, 7.0),
    ("Stair_L2_3", "Gate_L2_S_West", None, 7.5),
    ("Stair_L2_3", "Gate_L2_S_East", None, 7.5),
]

L2_VERTICAL_TO_VIRTUAL = [
    ("Stair_L2_1", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_up1", "VN_L2_Corner_1", None, 7.0),
    ("Stair_L2_2", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_up2", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_up3", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_down1", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_down2", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_up4", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_up5", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_down3", "VN_L2_Corner_1", None, 7.0),
    ("Escalator_L2_up6", "VN_L2_Corner_1", None, 7.0),
    ("Stair_L2_3", "VN_L2_Corner_1", None, 7.0),
]

L2_GATE_TO_EXIT = [
    ("Gate_L2_N_West", "Exit_L2_2", None, 7.54),
    ("Gate_L2_N_East", "Exit_L2_6", None, 5.2),
    ("Gate_L2_S_West", "Exit_L2_4", None, 7.6),
    ("Gate_L2_S_East", "Exit_L2_3", None, 4.2),
]

L2_VIRTUAL_TO_GATE = [
    ("VN_L2_Corner_1", "Gate_L2_N_East", None, None),
]

# ---------------------------------------------------------
# [3.3] 16号线边关系 (全自动笛卡尔积连线)
# ---------------------------------------------------------
_l16_verts = [
    "Stair_L16_1", "Escalator_L16_up1", "Escalator_L16_down1", "Escalator_L16_down2",
    "Stair_L16_2", "Escalator_L16_up2", "Escalator_L16_up3", "Stair_L16_3",
    "Escalator_L16_down3", "Escalator_L16_down4", "Escalator_L16_up4", "Stair_L16_4"
]
_l16_gates = ["Gate_L16_N1", "Gate_L16_N2", "Gate_L16_S1", "Gate_L16_S2"]
_l16_exits = ["Exit_L16_10", "Exit_L16_11"]

L16_VERTICAL_TO_GATE = [(v, g, None, None) for v in _l16_verts for g in _l16_gates]
L16_GATE_TO_EXIT = [(g, e, None, None) for g in _l16_gates for e in _l16_exits]

# ---------------------------------------------------------
# [3.4] 18号线边关系 (全自动笛卡尔积连线)
# ---------------------------------------------------------
_l18_verts = [
    "Escalator_L18_down1", "Escalator_L18_up1", "Stair_L18_1", "Escalator_L18_up2",
    "Escalator_L18_down2", "Escalator_L18_up3", "Escalator_L18_down3", "Escalator_L18_up4",
    "Escalator_L18_up5", "Escalator_L18_up6", "Stair_L18_2", "Escalator_L18_down4",
    "Escalator_L18_up7", "Escalator_L18_up8", "Escalator_L18_up9"
]
_l18_gates = ["Gate_L18_E1", "Gate_L18_E2", "Gate_L18_S1", "Gate_L18_S2"]
_l18_exits_entrances = ["VN_L18_Exit12_Entrance", "VN_L18_Exit17_Entrance", "VN_L18_Exit13_Entrance"]

L18_VERTICAL_TO_GATE = [(v, g, None, None) for v in _l18_verts for g in _l18_gates]
L18_GATE_TO_EXIT_ENTRANCE = [(g, e, None, None) for g in _l18_gates for e in _l18_exits_entrances]

L18_EXIT_INTERNAL_EDGES = [
    # 12号口内部拓扑
    ("VN_L18_Exit12_Entrance", "Stair_L18_Exit12", None, 7.0, "exit_channel"),
    ("VN_L18_Exit12_Entrance", "Escalator_L18_Exit12_up1", None, 7.0, "exit_channel"),
    ("VN_L18_Exit12_Entrance", "Escalator_L18_Exit12_up2", None, 7.0, "exit_channel"),
    ("Stair_L18_Exit12", "Exit_L18_12", 22.0, 1.7, "exit_out"),
    ("Escalator_L18_Exit12_up1", "Exit_L18_12", 22.0, 1.0, "exit_out"),
    ("Escalator_L18_Exit12_up2", "Exit_L18_12", 22.0, 1.0, "exit_out"),

    # 17号口内部拓扑
    ("VN_L18_Exit17_Entrance", "Stair_L18_Exit17", None, 6.5, "exit_channel"),
    ("VN_L18_Exit17_Entrance", "Escalator_L18_Exit17_up1", None, 6.5, "exit_channel"),
    ("VN_L18_Exit17_Entrance", "Escalator_L18_Exit17_up2", None, 6.5, "exit_channel"),
    ("Stair_L18_Exit17", "Exit_L18_17", 22.0, 1.7, "exit_out"),
    ("Escalator_L18_Exit17_up1", "Exit_L18_17", 22.0, 1.0, "exit_out"),
    ("Escalator_L18_Exit17_up2", "Exit_L18_17", 22.0, 1.0, "exit_out"),

    # 13号口内部拓扑 (纯长通道)
    ("VN_L18_Exit13_Entrance", "Exit_L18_13", None, 6.0, "exit_channel"),
]

# ---------------------------------------------------------
# [3.5] 磁悬浮边关系
# ---------------------------------------------------------
_maglev_gates = ["Gate_Maglev_W1", "Gate_Maglev_W2", "Gate_Maglev_W3", "Gate_Maglev_E1"]
_maglev_exits = [
    "Stair_Maglev_Exit18", "Escalator_Maglev_Exit18",
    "Stair_Maglev_Exit19", "Escalator_Maglev_Exit19",
    "Stair_Maglev_Exit20", "Escalator_Maglev_Exit20",
    "Stair_Maglev_Exit21", "Escalator_Maglev_Exit21"
]

MAGLEV_VERTICAL_TO_GATE = [
    ("Escalator_Maglev_down1", "Gate_Maglev_W1", None, 11.7),
    ("Stair_Maglev_1", "Gate_Maglev_W1", None, 11.7),
    ("Escalator_Maglev_down3", "Gate_Maglev_W3", None, 12.0),
    ("Stair_Maglev_3", "Gate_Maglev_W3", None, 12.0),
    ("Escalator_Maglev_up1", "Gate_Maglev_W2", None, 12.0),
    ("Stair_Maglev_5", "Gate_Maglev_W2", None, 12.0),
    ("Escalator_Maglev_up2", "Gate_Maglev_E1", None, 12.0),
    ("Stair_Maglev_6", "Gate_Maglev_E1", None, 12.0),
]

MAGLEV_GATE_TO_EXIT_VERT = [
    (gate, exit_node, None, 25.5) for gate in _maglev_gates for exit_node in _maglev_exits
]

MAGLEV_VERTICAL_TO_EXIT = [
    ("Stair_Maglev_Exit18", "Exit_Maglev_18", None, None),
    ("Escalator_Maglev_Exit18", "Exit_Maglev_18", None, None),
    ("Stair_Maglev_Exit19", "Exit_Maglev_19", None, None),
    ("Escalator_Maglev_Exit19", "Exit_Maglev_19", None, None),
    ("Stair_Maglev_Exit20", "Exit_Maglev_20", None, None),
    ("Escalator_Maglev_Exit20", "Exit_Maglev_20", None, None),
    ("Stair_Maglev_Exit21", "Exit_Maglev_21", None, None),
    ("Escalator_Maglev_Exit21", "Exit_Maglev_21", None, None),
]

# ==============================================================================
# 模块 4：跨线换乘关系及总体装配 (TRANSFERS & BUILD)
# ==============================================================================

# ---------------------------------------------------------
# [4.1] 垂直换乘设施到入口的映射 (Vertical to Transfer)
# ---------------------------------------------------------
L2_VERTICAL_TO_L16_TRANSFER = [
    ("Stair_L2_1", "VN_L2_to_L16_Entrance", None, None),
    ("Stair_L2_2", "VN_L2_to_L16_Entrance", None, None),
    ("Stair_L2_3", "VN_L2_to_L16_Entrance", None, None),
    ("Stair_L2_4", "VN_L2_to_L16_Entrance", None, None),
    ("Stair_L2_5", "VN_L2_to_L16_Entrance", None, None),
    ("Stair_L2_6", "VN_L2_to_L16_Entrance", None, None),
    ("Escalator_L2_up1", "VN_L2_to_L16_Entrance", None, None),
    ("Escalator_L2_down1", "VN_L2_to_L16_Entrance", None, None),
]

L16_VERTICAL_TO_TRANSFER = [
    (v, "VN_L16_to_Maglev_Entrance", None, None) for v in _l16_verts
]

L18_VERTICAL_TO_TRANSFER = [
    (v, "VN_L18_to_L16_Entrance", None, None) for v in _l18_verts
]

MAGLEV_VERTICAL_TO_TRANSFER = [
    ("Escalator_Maglev_down2", "VN_Maglev_to_L2_Entrance", None, 13),
    ("Stair_Maglev_2", "VN_Maglev_to_L2_Entrance", None, 13),
    ("Escalator_Maglev_down4", "VN_Maglev_to_L2_Entrance", None, 7),
    ("Stair_Maglev_4", "VN_Maglev_to_L2_Entrance", None, 7),
]

# ---------------------------------------------------------
# [4.2] 换乘到达后站厅分流闸机
# ---------------------------------------------------------
TRANSFER_ARRIVAL_TO_L2_GATES = [
    ("VN_L7toL2_Hall_Arrival", "Gate_L2_N_West", None, None),
    ("VN_L7toL2_Hall_Arrival", "Gate_L2_N_East", None, None),
    ("VN_L7toL2_Hall_Arrival", "Gate_L2_S_West", None, None),
    ("VN_L7toL2_Hall_Arrival", "Gate_L2_S_East", None, None),

    ("VN_Maglev_to_L2_Arrival", "Gate_L2_N_West", None, None),
    ("VN_Maglev_to_L2_Arrival", "Gate_L2_N_East", None, None),
    ("VN_Maglev_to_L2_Arrival", "Gate_L2_S_West", None, None),
    ("VN_Maglev_to_L2_Arrival", "Gate_L2_S_East", None, None),
]

# ---------------------------------------------------------
# [4.3] 换乘核心通道逻辑 (TRANSFER EDGES)
# ---------------------------------------------------------
TRANSFER_EDGES = [

    # --- 7号线 换 2号线 ---
    ("Stair_L7_1", "VN_7to2_Entrance", None, 10.0, "transfer_in"),
    ("Stair_L7_2", "VN_7to2_Entrance", None, 6.58, "transfer_in"),
    ("Stair_L7_3", "VN_7to2_Entrance", None, 6.58, "transfer_in"),
    ("Escalator_L7_up1", "VN_7to2_Entrance", None, 10.0, "transfer_in"),
    ("Escalator_L7_down1", "VN_7to2_Entrance", None, 10.0, "transfer_in"),
    ("VN_7to2_Entrance", "Transfer_L7-L2_Z", None, 6.77, "transfer_channel"),
    ("Transfer_L7-L2_Z", "Transfer_L7-L2_Stair", None, 7.6, "transfer_channel"),
    ("Transfer_L7-L2_Z", "Transfer_L7-L2_Esc1", None, 7.6, "transfer_channel"),
    ("Transfer_L7-L2_Z", "Transfer_L7-L2_Esc2", None, 7.6, "transfer_channel"),
    ("Transfer_L7-L2_Stair", "VN_L7toL2_Hall_Arrival", None, None, "transfer_out"),
    ("Transfer_L7-L2_Esc1", "VN_L7toL2_Hall_Arrival", None, None, "transfer_out"),
    ("Transfer_L7-L2_Esc2", "VN_L7toL2_Hall_Arrival", None, None, "transfer_out"),

    # --- 2号线 换 7号线 ---
    ("Platform_L2", "Transfer_L2-L7_Passageway", None, 7.7, "transfer_in"),
    ("Transfer_L2-L7_Passageway", "VN_2to7_Exit", None, 7.7, "transfer_channel"),
    ("VN_2to7_Exit", "Gate_L7_N_West", None, 6.58, "transfer_out"),
    ("VN_2to7_Exit", "Gate_L7_N_Mid", None, 6.58, "transfer_out"),
    ("VN_2to7_Exit", "Gate_L7_N_East", None, 6.58, "transfer_out"),
    ("VN_2to7_Exit", "Gate_L7_West_Vert", None, 6.58, "transfer_out"),

    # --- 站厅平行直走 (7->2站厅 & Maglev->2站厅 去换乘16号线) ---
    ("VN_L7toL2_Hall_Arrival", "VN_L2_to_L16_Entrance", None, None, "transfer_channel"),
    ("VN_Maglev_to_L2_Arrival", "VN_L2_to_L16_Entrance", None, None, "transfer_channel"),

    # --- 磁悬浮 换 2号线 ---
    ("VN_Maglev_to_L2_Entrance", "Transfer_Maglev_L2_Esc1", None, None, "transfer_channel"),
    ("VN_Maglev_to_L2_Entrance", "Transfer_Maglev_L2_Esc2", None, None, "transfer_channel"),
    ("VN_Maglev_to_L2_Entrance", "Transfer_Maglev_L2_Esc3", None, None, "transfer_channel"),
    ("VN_Maglev_to_L2_Entrance", "Transfer_Maglev_L2_Stair", None, None, "transfer_channel"),
    ("Transfer_Maglev_L2_Esc1", "VN_Maglev_to_L2_Arrival", None, 14, "transfer_out"),
    ("Transfer_Maglev_L2_Esc2", "VN_Maglev_to_L2_Arrival", None, 14, "transfer_out"),
    ("Transfer_Maglev_L2_Esc3", "VN_Maglev_to_L2_Arrival", None, 14, "transfer_out"),
    ("Transfer_Maglev_L2_Stair", "VN_Maglev_to_L2_Arrival", None, 14, "transfer_out"),

    # --- 2号线 换 16号线 (包含梯形天桥处理) ---
    ("VN_L2_to_L16_Entrance", "Transfer_L2_L16_Esc1", 15, None, "transfer_channel"),
    ("VN_L2_to_L16_Entrance", "Transfer_L2_L16_Esc2", 15, None, "transfer_channel"),
    ("VN_L2_to_L16_Entrance", "Transfer_L2_L16_Esc3", 15, None, "transfer_channel"),
    ("VN_L2_to_L16_Entrance", "Transfer_L2_L16_Esc4", 15, None, "transfer_channel"),
    ("Transfer_L2_L16_Esc1", "VN_L2_to_L16_Passageway_Start", None, None, "transfer_channel"),
    ("Transfer_L2_L16_Esc2", "VN_L2_to_L16_Passageway_Start", None, None, "transfer_channel"),
    ("Transfer_L2_L16_Esc3", "VN_L2_to_L16_Passageway_Start", None, None, "transfer_channel"),
    ("Transfer_L2_L16_Esc4", "VN_L2_to_L16_Passageway_Start", None, None, "transfer_channel"),
    ("VN_L2_to_L16_Passageway_Start", "VN_L2_to_L16_Passageway_End", 34.0, 13.5, "transfer_channel"),
    ("VN_L2_to_L16_Passageway_End", "VN_L2_to_L16_Bridge_Trapezoid", None, 14.0, "transfer_channel"),
    ("VN_L2_to_L16_Bridge_Trapezoid", "VN_L2_to_L16_Hall_Arrival", 41, 18, "transfer_channel"),
    ("VN_L2_to_L16_Hall_Arrival", "Gate_L16_N1", None, None, "transfer_out"),
    ("VN_L2_to_L16_Hall_Arrival", "Gate_L16_N2", None, None, "transfer_out"),
    ("VN_L2_to_L16_Hall_Arrival", "Gate_L16_S1", None, None, "transfer_out"),
    ("VN_L2_to_L16_Hall_Arrival", "Gate_L16_S2", None, None, "transfer_out"),

    # --- 16号线 借道磁悬浮大厅 换 2号线 ---
    ("VN_L16_to_Maglev_Entrance", "Transfer_L16_Maglev_Passageway", 26.0, 13.0, "transfer_channel"),
    ("Transfer_L16_Maglev_Passageway", "VN_L16_to_Maglev_Arrival", None, 7.2, "transfer_channel"),
    ("VN_L16_to_Maglev_Arrival", "VN_Maglev_to_L2_Entrance", None, 13, "transfer_channel"),

    # --- 换乘18号线的向下拓扑 (Y字型漏斗: 2/7号线左路 + 16号线右路) ---
    ("VN_L2_to_L16_Bridge_Trapezoid", "VN_L2_to_L18_Transfer_Start", None, 12.3, "transfer_channel"),
    ("VN_L2_to_L16_Hall_Arrival", "VN_L16_to_L18_Transfer_Start", None, 19, "transfer_channel"),

    # 漏斗左路 (3扶1梯 -> 异形中间平台 A端)
    ("VN_L2_to_L18_Transfer_Start", "Transfer_L2_L18_F1_Esc1", None, 10.4, "transfer_channel"),
    ("VN_L2_to_L18_Transfer_Start", "Transfer_L2_L18_F1_Esc2", None, 10.4, "transfer_channel"),
    ("VN_L2_to_L18_Transfer_Start", "Transfer_L2_L18_F1_Esc3", None, 10.4, "transfer_channel"),
    ("VN_L2_to_L18_Transfer_Start", "Transfer_L2_L18_F1_Stair", None, 10.4, "transfer_channel"),
    ("Transfer_L2_L18_F1_Esc1", "VN_L18_Mid_Platform_A", 22.0, 1.0, "transfer_out"),
    ("Transfer_L2_L18_F1_Esc2", "VN_L18_Mid_Platform_A", 22.0, 1.0, "transfer_out"),
    ("Transfer_L2_L18_F1_Esc3", "VN_L18_Mid_Platform_A", 22.0, 1.0, "transfer_out"),
    ("Transfer_L2_L18_F1_Stair", "VN_L18_Mid_Platform_A", 22.0, 1.7, "transfer_out"),

    # 漏斗右路 (2扶1梯 -> 异形中间平台 B端)
    ("VN_L16_to_L18_Transfer_Start", "Transfer_L16_L18_F1_Esc1", None, None, "transfer_channel"),
    ("VN_L16_to_L18_Transfer_Start", "Transfer_L16_L18_F1_Esc2", None, None, "transfer_channel"),
    ("VN_L16_to_L18_Transfer_Start", "Transfer_L16_L18_F1_Stair", None, None, "transfer_channel"),
    ("Transfer_L16_L18_F1_Esc1", "VN_L18_Mid_Platform_B", 22.0, 1.0, "transfer_out"),
    ("Transfer_L16_L18_F1_Esc2", "VN_L18_Mid_Platform_B", 22.0, 1.0, "transfer_out"),
    ("Transfer_L16_L18_F1_Stair", "VN_L18_Mid_Platform_B", 22.0, 1.7, "transfer_out"),

    # 从 平台左端(A) 走向全部7个下行通道
    ("VN_L18_Mid_Platform_A", "Transfer_Mid_L18_F2_Left_Esc1", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_A", "Transfer_Mid_L18_F2_Left_Esc2", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_A", "Transfer_Mid_L18_F2_Left_Esc3", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_A", "Transfer_Mid_L18_F2_Left_Esc4", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_A", "Transfer_Mid_L18_F2_Right_Esc1", None, 8.5, "transfer_channel"),
    ("VN_L18_Mid_Platform_A", "Transfer_Mid_L18_F2_Right_Esc2", None, 8.5, "transfer_channel"),
    ("VN_L18_Mid_Platform_A", "Transfer_Mid_L18_F2_Right_Stair", None, 8.5, "transfer_channel"),

    # 从 平台右端(B) 走向全部7个下行通道
    ("VN_L18_Mid_Platform_B", "Transfer_Mid_L18_F2_Left_Esc1", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_B", "Transfer_Mid_L18_F2_Left_Esc2", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_B", "Transfer_Mid_L18_F2_Left_Esc3", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_B", "Transfer_Mid_L18_F2_Left_Esc4", None, 10.0, "transfer_channel"),
    ("VN_L18_Mid_Platform_B", "Transfer_Mid_L18_F2_Right_Esc1", None, 8.5, "transfer_channel"),
    ("VN_L18_Mid_Platform_B", "Transfer_Mid_L18_F2_Right_Esc2", None, 8.5, "transfer_channel"),
    ("VN_L18_Mid_Platform_B", "Transfer_Mid_L18_F2_Right_Stair", None, 8.5, "transfer_channel"),

    # 下沉到底层18号线站厅
    ("Transfer_Mid_L18_F2_Left_Esc1", "VN_L18_Hall_Arrival_Base", 22.0, 1.0, "transfer_out"),
    ("Transfer_Mid_L18_F2_Left_Esc2", "VN_L18_Hall_Arrival_Base", 22.0, 1.0, "transfer_out"),
    ("Transfer_Mid_L18_F2_Left_Esc3", "VN_L18_Hall_Arrival_Base", 22.0, 1.0, "transfer_out"),
    ("Transfer_Mid_L18_F2_Left_Esc4", "VN_L18_Hall_Arrival_Base", 22.0, 1.0, "transfer_out"),
    ("Transfer_Mid_L18_F2_Right_Esc1", "VN_L18_Hall_Arrival_Base", 22.0, 1.0, "transfer_out"),
    ("Transfer_Mid_L18_F2_Right_Esc2", "VN_L18_Hall_Arrival_Base", 22.0, 1.0, "transfer_out"),
    ("Transfer_Mid_L18_F2_Right_Stair", "VN_L18_Hall_Arrival_Base", 22.0, 1.7, "transfer_out"),

    # 18号线站厅分流 (被墙体隔开的两个通道)
    ("VN_L18_Hall_Arrival_Base", "VN_L18_Hall_Split_A", None, 6.5, "transfer_channel"),
    ("VN_L18_Hall_Arrival_Base", "VN_L18_Hall_Split_B", None, 6.5, "transfer_channel"),
    ("VN_L18_Hall_Split_A", "Gate_L18_E1", None, None, "transfer_out"),
    ("VN_L18_Hall_Split_A", "Gate_L18_E2", None, None, "transfer_out"),
    ("VN_L18_Hall_Split_B", "Gate_L18_S1", None, None, "transfer_out"),
    ("VN_L18_Hall_Split_B", "Gate_L18_S2", None, None, "transfer_out"),

    # --- 18号线出发 换 16号线 ---
    ("VN_L18_to_L16_Entrance", "VN_L18_to_L16_Split_A", None, 6, "transfer_channel"),
    ("VN_L18_to_L16_Entrance", "VN_L18_to_L16_Split_B", None, 6, "transfer_channel"),
    ("VN_L18_to_L16_Split_A", "VN_L18_to_L16_Merge", None, 6, "transfer_channel"),
    ("VN_L18_to_L16_Split_B", "VN_L18_to_L16_Merge", None, 6, "transfer_channel"),

    # 底部爬到中转平层
    ("VN_L18_to_L16_Merge", "Transfer_L18_L16_F1_Stair", None, 15.0, "transfer_channel"),
    ("VN_L18_to_L16_Merge", "Transfer_L18_L16_F1_Esc1", None, 15.0, "transfer_channel"),
    ("VN_L18_to_L16_Merge", "Transfer_L18_L16_F1_Esc2", None, 15.0, "transfer_channel"),
    ("VN_L18_to_L16_Merge", "Transfer_L18_L16_F1_Esc3", None, 15.0, "transfer_channel"),
    ("VN_L18_to_L16_Merge", "Transfer_L18_L16_F1_Esc4", None, 15.0, "transfer_channel"),
    ("Transfer_L18_L16_F1_Stair", "VN_L18_to_L16_Mid_Platform_Start", None, 2.0, "transfer_out"),
    ("Transfer_L18_L16_F1_Esc1", "VN_L18_to_L16_Mid_Platform_Start", None, 1.0, "transfer_out"),
    ("Transfer_L18_L16_F1_Esc2", "VN_L18_to_L16_Mid_Platform_Start", None, 1.0, "transfer_out"),
    ("Transfer_L18_L16_F1_Esc3", "VN_L18_to_L16_Mid_Platform_Start", None, 1.0, "transfer_out"),
    ("Transfer_L18_L16_F1_Esc4", "VN_L18_to_L16_Mid_Platform_Start", None, 1.0, "transfer_out"),
    ("VN_L18_to_L16_Mid_Platform_Start", "VN_L18_to_L16_Mid_Platform_End", None, 12.0, "transfer_channel"),

    # 中转平层爬到顶部
    ("VN_L18_to_L16_Mid_Platform_End", "Transfer_L18_L16_F2_Stair", None, 2.0, "transfer_channel"),
    ("VN_L18_to_L16_Mid_Platform_End", "Transfer_L18_L16_F2_Esc1", None, 1.0, "transfer_channel"),
    ("VN_L18_to_L16_Mid_Platform_End", "Transfer_L18_L16_F2_Esc2", None, 1.0, "transfer_channel"),
    ("VN_L18_to_L16_Mid_Platform_End", "Transfer_L18_L16_F2_Esc3", None, 1.0, "transfer_channel"),
    ("VN_L18_to_L16_Mid_Platform_End", "Transfer_L18_L16_F2_Esc4", None, 1.0, "transfer_channel"),
    ("Transfer_L18_L16_F2_Stair", "VN_L18_to_L16_Hall_Arrival", None, None, "transfer_out"),
    ("Transfer_L18_L16_F2_Esc1", "VN_L18_to_L16_Hall_Arrival", None, None, "transfer_out"),
    ("Transfer_L18_L16_F2_Esc2", "VN_L18_to_L16_Hall_Arrival", None, None, "transfer_out"),
    ("Transfer_L18_L16_F2_Esc3", "VN_L18_to_L16_Hall_Arrival", None, None, "transfer_out"),
    ("Transfer_L18_L16_F2_Esc4", "VN_L18_to_L16_Hall_Arrival", None, None, "transfer_out"),

    # 18换16 最终分流
    ("VN_L18_to_L16_Hall_Arrival", "VN_L16_to_Maglev_Entrance", None, 14.0, "transfer_channel"),
    ("VN_L18_to_L16_Hall_Arrival", "Gate_L16_N1", None, None, "transfer_out"),
    ("VN_L18_to_L16_Hall_Arrival", "Gate_L16_N2", None, None, "transfer_out"),
    ("VN_L18_to_L16_Hall_Arrival", "Gate_L16_S1", None, None, "transfer_out"),
    ("VN_L18_to_L16_Hall_Arrival", "Gate_L16_S2", None, None, "transfer_out"),
]


# ---------------------------------------------------------
# [4.4] 装配函数
# ---------------------------------------------------------
def build_edges_data():
    edges = []

    # 7号线单线网
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_gate") for u, v, l, w in L7_VERTICAL_TO_GATE]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="gate_to_virtual") for u, v, l, w in L7_GATE_TO_VIRTUAL]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="virtual_to_exit") for u, v, l, w in L7_VIRTUAL_TO_EXIT]

    # 2号线单线网
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_gate") for u, v, l, w in L2_VERTICAL_TO_GATE]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_virtual") for u, v, l, w in
              L2_VERTICAL_TO_VIRTUAL]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="gate_to_exit") for u, v, l, w in L2_GATE_TO_EXIT]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="virtual_to_gate") for u, v, l, w in L2_VIRTUAL_TO_GATE]

    # 磁悬浮单线网
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_gate") for u, v, l, w in
              MAGLEV_VERTICAL_TO_GATE]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="gate_to_vertical") for u, v, l, w in
              MAGLEV_GATE_TO_EXIT_VERT]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_exit") for u, v, l, w in
              MAGLEV_VERTICAL_TO_EXIT]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_transfer") for u, v, l, w in
              MAGLEV_VERTICAL_TO_TRANSFER]

    # 16号线单线网
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_gate") for u, v, l, w in L16_VERTICAL_TO_GATE]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="gate_to_exit") for u, v, l, w in L16_GATE_TO_EXIT]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_transfer") for u, v, l, w in
              L16_VERTICAL_TO_TRANSFER]

    # 18号线单线网
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_gate") for u, v, l, w in L18_VERTICAL_TO_GATE]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="gate_to_virtual") for u, v, l, w in
              L18_GATE_TO_EXIT_ENTRANCE]
    edges += [edge(u, v, length=l, width_limit=w, edge_type=etype) for u, v, l, w, etype in L18_EXIT_INTERNAL_EDGES]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_transfer") for u, v, l, w in
              L18_VERTICAL_TO_TRANSFER]

    # 跨线连接及换乘设施网
    edges += [edge(u, v, length=l, width_limit=w, edge_type="vertical_to_transfer") for u, v, l, w in
              L2_VERTICAL_TO_L16_TRANSFER]
    edges += [edge(u, v, length=l, width_limit=w, edge_type="transfer_to_gate") for u, v, l, w in
              TRANSFER_ARRIVAL_TO_L2_GATES]
    edges += [edge(u, v, length=l, width_limit=w, edge_type=etype) for u, v, l, w, etype in TRANSFER_EDGES]

    return edges


EDGES_DATA = build_edges_data()

PRECALCULATED_PLATFORM_DISTS = {
    "Stair_L7_1": 40.26,
    "Escalator_L7_up1": 41.34,
    "Stair_L7_2": 35.24,
    "Stair_L7_3": 42.03,
    "Escalator_L7_down1": 42.09,
    "Stair_L2_1": 60.85,
    "Stair_L2_2": 61.42,
    "Stair_L2_3": 46.33,
    "Escalator_L2_up1": 47.07,
    "Escalator_L2_down1": 49.06,
    "Stair_L2_4": 49.35,
    "Stair_L2_5": 63.28,
    "Stair_L2_6": 63.85,
    "Stair_L16_1": 44.88,
    "Escalator_L16_up1": 45.34,
    "Escalator_L16_down1": 38.24,
    "Escalator_L16_down2": 38.94,
    "Stair_L16_2": 44.55,
    "Escalator_L16_up2": 45.09,
    "Escalator_L16_up3": 44.55,
    "Stair_L16_3": 45.28,
    "Escalator_L16_down3": 38.14,
    "Escalator_L16_down4": 38.71,
    "Escalator_L16_up4": 44.34,
    "Stair_L16_4": 45.04,
    "Escalator_L18_down1": 48.71,
    "Escalator_L18_up1": 49.01,
    "Stair_L18_1": 49.61,
    "Escalator_L18_up2": 50.11,
    "Escalator_L18_down2": 36.76,
    "Escalator_L18_up3": 37.23,
    "Escalator_L18_down3": 36.86,
    "Escalator_L18_up4": 36.32,
    "Escalator_L18_up5": 35.85,
    "Escalator_L18_down4": 46.7,
    "Stair_L18_2": 45.97,
    "Escalator_L18_up6": 45.51,
    "Escalator_L18_up7": 58.17,
    "Escalator_L18_up8": 57.7,
    "Escalator_L18_up9": 57.18,
    "Escalator_Maglev_down1": 54.83,
    "Stair_Maglev_1": 54.82,
    "Escalator_Maglev_down2": 41.75,
    "Stair_Maglev_2": 41.21,
    "Stair_Maglev_3": 59.82,
    "Escalator_Maglev_down3": 60.66,
    "Stair_Maglev_4": 47.04,
    "Escalator_Maglev_down4": 48.03,
    "Stair_Maglev_5": 81.86,
    "Escalator_Maglev_up1": 81.78,
    "Stair_Maglev_6": 37.62,
    "Escalator_Maglev_up2": 36.98,
}

# ======================================================================
# 可选：障碍物配置
# - nodes: 可选，若某个站台/节点内部存在遮挡，可压缩节点有效面积
# - edges: 推荐，用于表示走廊/通道上的障碍物，占用该边的有效通行面积
# 结构示例：
# OBSTACLE_AREAS = {
#     "nodes": {
#         "L2": {
#             "Stair_L2_3": 8.0,
#         }
#     },
#     "edges": {
#         "L2": {
#             "VN_L7_Corner_1 -> Exit_L7_8/9": 6.9,
#         }
#     }
# }
# ======================================================================
OBSTACLE_AREAS = {
    "nodes": {
        "L2": {},
        "L7": {},
        "L16": {},
        "L18": {},
        "Maglev": {},
    },
    "edges": {
        "L7": {
            "VN_L7_Corner_1 -> Exit_L7_8/9": 6.9,
        },
        "L2": {},
        "L16": {},
        "L18": {},
        "Maglev": {},
    },
}

