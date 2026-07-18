# 恋恋挂件 — 外部求援背景简报

## 项目本质

Windows 桌面挂件精灵（.NET WinForms + WPF 透明叠加层）。一个 GIF 动画挂饰通过 Verlet 积分绳索悬挂在鼠标光标上，受重力摆动物理驱动。类似桌面宠物，但不响应鼠标位置——挂件锚点直接绑定光标。

## 技术栈

- **运行时**：.NET Framework 4.x, WinForms (Form1 主控) + WPF (WpfPendantOverlayWindow 透明渲染)
- **物理引擎**：自研 Engine3 — Verlet 积分 + 距离约束求解 + 静止冻结检测
- **渲染**：GDI+ (DrawPendant/Rope) 和 WPF DrawingVisual 双路径；支持 OBS 捕获 (Direct3D 11 交换链)
- **修改方式**：Mono.Cecil IL 注入（无源码，逆向编译后 .NET 程序集）

## 绳索物理 (Engine3) 概览

```
锚点(光标) → [绳段0] → [绳段1] → ... → [绳段N-1] → 挂饰末点
  索引0        索引1      索引2              索引N
```

- Verlet 积分：`newPos = pos + (pos - oldPos) * damping + gravity * dt²`
- 距离约束：迭代求解，保持相邻点间距 = segmentLength
- 静止检测：锚点移动 < 0.05px + 绳索角度偏差 < 1° 持续 0.8s → 冻结物理
- 参数：阻尼 0.9985，重力缩放 0.6，锚点速度传递 0.56

## 已修补内容 (IL 注入)

1. **DWM 阴影消除**：禁用叠加窗口的非客户区渲染
2. **光标隐藏保活**：光标隐藏时保持挂件可见
3. **屏幕边缘夹持**：`Max(0, Min(X, screenW))` + `Max(0, Min(Y, screenH-20))`
4. **窗口碰撞**：WinPlat.dll 枚举顶层窗口 + 任务栏，pendant 落在标题栏/任务栏上
5. **参数调优**：阻尼 0.997→0.9985，静止延迟 0.3s→0.8s
6. **微扰动**：冻结态注入 ±0.5px 锯齿波漂移（300 帧周期）

## 当前状态

- 基本功能可用，但物理真实感和行为丰富度有提升空间
- IL 注入路线可行但每轮修改成本高
- 无源码，对原始程序集内部逻辑的认知来自 IL 逆向

## 关键源码文件

- `build_r1.py`：IL 注入构建脚本（约 300 行 Python + Mono.Cecil）
- `WindowPlatforms.cs`：WinPlat.dll 源码（窗口枚举 + 任务栏检测）
- 原始 EXE：`恋恋挂件-本地测试版-v1.exe`（.NET PE, 约 647KB, WinForms+WPF 混合程序集）
