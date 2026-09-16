# Listing Generator

> AI 驱动的 Amazon Listing 视觉生成 Skill  
> 从产品图片与需求描述出发，完成产品分析、卖点提取、Listing 图片规划、视觉模板选择、Prompt 生成，并在配置图片生成能力后执行 AI 生图。

Listing Generator 面向跨境电商 Listing 视觉内容制作场景，核心不是简单生成一张商品图，而是将：

**产品分析 → 卖点提取 → 转化驱动力分析 → Listing 图片规划 → 模板选择 → 视觉风格统一 → Prompt → QA → AI 生图**

串联为一套可重复使用的工作流。

---

## ✨ 核心能力

### 1. 产品分析

根据用户提供的产品图片、文字描述及产品资料，提取：

- 产品名称与品类
- 产品类型
- 颜色与外观
- 材质与结构
- 可见功能特征
- 核心卖点
- 目标用户
- 使用场景
- 产品视觉风格

同时区分产品信息的可信度：

- **Confirmed**：用户文字或图片可以直接确认
- **Inferred**：AI 根据图片或品类进行推断
- **Unknown**：当前信息无法确认

对于无法确认的参数、认证、性能、兼容性等信息，不将推断内容直接当作产品事实。

### 2. Selling Point 提取

最多提取 5 个核心卖点，并将每个卖点拆分为：

```text
Feature
    ↓
Customer Benefit
    ↓
Visual Proof
```

让产品卖点能够进一步转换为 Listing 图片中的视觉表达。

### 3. Conversion Driver 诊断

根据产品特点判断主要购买驱动力：

| 类型 | 适用场景 |
| --- | --- |
| Visual-driven | 外观、设计、质感、家居、美妆、饰品等 |
| Pain-point-driven | 清洁、收纳、保护、效率、工具等 |
| Emotional-value-driven | 礼品、时尚、宠物、儿童、身份表达等 |

再根据购买驱动力规划更匹配的视觉内容。

---

## 🖼 Amazon Listing 图片规划

针对 Amazon Listing，默认规划 5 张核心图片：

| 图片 | 目的 |
| --- | --- |
| **H1** | Hero / Product，明确展示产品 |
| **H2** | Core Benefit，突出核心卖点 |
| **H3** | Lifestyle / Usage，展示使用场景 |
| **H4** | Comparison / Differentiation，展示差异化 |
| **H5** | Detail / Secondary Benefit，展示细节或第二卖点 |

如果需要完整 PDP / A+ 视觉内容，则继续规划：

| 图片 | 目的 |
| --- | --- |
| D1 | Problem / Need |
| D2 | Solution |
| D3 | Product Mechanism |
| D4 | Core Benefits |
| D5 | How to Use |
| D6 | Usage Scenarios |
| D7 | Comparison |
| D8 | Trust / Quality |
| D9 | FAQ / CTA |

图片结构会根据具体产品进行调整，而不是机械套用固定模板。

---

## 🎨 视觉模板

项目包含一套电商视觉模板库，共 25 类视觉模板，用于根据产品、卖点、图片用途及 Listing 目标选择合适的视觉表达方式。

包括：

1. Hero Image
2. Lifestyle Scene
3. Flat Lay
4. Detail Macro
5. Poster Banner
6. Social Media
7. UGC Style
8. Model Showcase
9. Before / After
10. Packaging
11. Infographic
12. Creative Concept
13. Size / Specification
14. Multi Product
15. Livestream
16. Virtual Try-on
17. Exploded View
18. Ghost Mannequin
19. Multi-angle Grid
20. Magazine Editorial
21. Seasonal Campaign
22. Luxury Atmospherics
23. Device Mockup
24. Storefront
25. Sports Campaign

模板并非要求一套 Listing 全部使用，而是根据图片目的和产品卖点进行选择。

---

## 🎯 Campaign Style Lock

为了让同一套 Listing 图片保持统一的视觉风格，工作流会建立 Campaign Style Lock，对以下视觉要素进行统一：

- Visual Direction
- Color Palette
- Temperature
- Typography
- Background
- Lighting
- Layout
- Product Presentation
- Whitespace
- Forbidden Drift

这样可以降低批量生成时出现的产品外观变化、颜色漂移、光线不一致、背景风格不统一及构图风格不一致等问题。

---

## 🧩 Structured Listing Plan

在正式生成 Prompt 和图片前，先形成结构化 Listing Plan，作为后续流程的中间状态。

主要包含：

```text
Product Evidence
├── Confirmed
├── Inferred
└── Unknown

Core Selling Points
├── Feature
├── Customer Benefit
├── Visual Proof
└── Evidence Level

Conversion Driver
├── Primary
└── Secondary

Campaign Style Lock
├── Visual Direction
├── Color Palette
├── Typography
├── Background
├── Lighting
├── Layout
└── Product Presentation

Listing Image Plan
├── Image ID
├── Amazon Image Purpose
├── Template ID
├── Selling Point
├── Composition
├── Camera Angle
├── Scene
├── Allowed Text
└── Negative Constraints
```

每张图片都会对应明确的 Template ID，后续 Prompt 与图片生成以结构化计划作为事实基准。

---

## 🔄 完整工作流

```text
User Input
    ↓
Product Analysis
    ↓
Evidence / Claim Gate
    ↓
Selling Point Extraction
    ↓
Conversion Driver Diagnosis
    ↓
Amazon Listing Image Planning
    ↓
Template Selection
    ↓
Campaign Style Lock
    ↓
Structured Listing Plan
    ↓
Prompt Generation
    ↓
Prompt QA
    ↓
User Confirmation
    ↓
Image Generation
    ↓
Image QA
    ↓
Prompt Repair / Retry
    ↓
Final Output
```

---

## 🤖 两种工作模式

### Planning / Prompt Mode

默认模式。当用户要求分析产品、规划 Listing、设计商品图或生成图片 Prompt，但没有明确要求立即出图时，只完成产品分析、卖点提取、购买驱动力分析、图片规划、模板选择、Campaign Style Lock、最终 Prompt 与 QA。

### Generate Mode

当用户明确要求生成、出图、开始生成、直接生成、render、generate 等操作时进入 Generate Mode：

```text
Structured Listing Plan
        ↓
读取对应 Template
        ↓
检查 Image Provider
        ↓
生成最终 Prompt
        ↓
Prompt QA
        ↓
调用图片生成能力
        ↓
保存图片与 Metadata
        ↓
Image QA
        ↓
PASS → 完成
FAIL → Prompt Repair / Retry
```

---

## 🛠 Python 工具链

项目包含两个主要 Python 脚本：

```text
scripts/
├── listing_plan.py
└── generate_image.py
```

### Listing Plan 校验

AI 完成初步规划后生成：

```text
scripts/listing_plan_draft.json
```

然后通过：

```bash
python scripts/listing_plan.py scripts/listing_plan_draft.json -o scripts/listing_plan.json
```

Windows 环境：

```bash
py scripts/listing_plan.py scripts/listing_plan_draft.json -o scripts/listing_plan.json
```

`listing_plan.py` 负责 Listing Plan 结构化、模板存在性检查、Evidence / Claim 风险检查及基础 Schema 校验。

### 图片生成

项目支持通过 `scripts/generate_image.py` 调用已经配置的图片生成能力。

使用产品参考图：

```bash
python3 scripts/generate_image.py \
  --prompt-file prompt.txt \
  --image data/product.jpg \
  --output-dir generated-images/product-listing
```

单图生成：

```bash
python3 scripts/generate_image.py \
  --prompt "clean premium product hero image" \
  --size 1024x1024
```

图片生成能力需要当前环境已经配置可用的 Image Provider / API。没有可用图片生成能力时，仍可以完成 Listing 规划与 Prompt 输出。

---

## 📁 项目结构

```text
Listing-Generator/
│
├── SKILL.md
├── scripts/
│   ├── listing_plan.py
│   └── generate_image.py
├── references/
│   └── templates/
│       ├── 01-hero-image.json
│       ├── 02-lifestyle-scene.json
│       └── ...
├── prompts/
├── data/
│   └── product/
└── generated-images/
```

| 目录 | 作用 |
| --- | --- |
| `SKILL.md` | AI Listing 工作流与执行规则 |
| `scripts/` | Listing Plan 校验及图片生成脚本 |
| `references/templates/` | 电商视觉模板库 |
| `prompts/` | Prompt 相关内容 |
| `data/product/` | 产品参考图片及相关输入数据 |
| `generated-images/` | 最终生成的图片 |

---

## 📦 输出结构

Amazon Listing 默认输出：

```text
generated-images/{product-slug}-amazon-listing/
├── H1-hero.png
├── H2-benefit.png
├── H3-lifestyle.png
├── H4-comparison.png
└── H5-detail.png
```

完整 PDP 默认输出：

```text
generated-images/{product-slug}-amazon-pdp/
├── H1-hero.png
├── H2-benefit.png
├── H3-lifestyle.png
├── H4-comparison.png
├── H5-detail.png
├── D1-problem.png
├── D2-solution.png
├── D3-mechanism.png
├── D4-benefits.png
├── D5-how-to-use.png
├── D6-lifestyle.png
├── D7-comparison.png
├── D8-trust.png
└── D9-cta.png
```

---

## 💡 适用场景

- Amazon Listing 主图
- Amazon PDP 商品详情图
- A+ 视觉素材规划
- 产品卖点图
- Lifestyle 场景图
- 产品信息图
- 社交媒体商品视觉素材
- UGC 风格商品图
- 电商营销视觉素材

---

## 🚀 快速开始

### 1. 准备产品图片

将产品参考图放入：

```text
data/product/
```

或者在支持图片输入的 AI Agent / Coding Agent 环境中直接提供产品图片。

### 2. 提出需求

例如：

```text
分析这个产品，并规划一套 Amazon Listing 图片。
```

或者：

```text
根据这个产品生成 5 张 Amazon Listing 主图。
```

也可以直接：

```text
一键生成这个产品的完整 Amazon Listing 图片。
```

### 3. AI 完成工作流

系统会依次完成：

```text
产品分析
→ 卖点提取
→ 转化驱动力分析
→ 图片规划
→ 模板选择
→ Campaign Style Lock
→ Prompt
→ QA
→ AI 生图
```

---

## ⚠️ 信息可信度规则

Listing Generator 强调产品信息的真实性。

禁止 AI 自行编造：

- 未提供的技术参数
- 未提供的认证
- 未提供的实验数据
- 未提供的销量
- 未提供的用户评价
- 未提供的品牌授权
- 未提供的专利
- 未提供的医疗功效
- 未提供的性能指标

例如用户没有提供 `72-hour battery`、`IP68`、`FDA approved`、`99.9% antibacterial`、`10,000+ reviews` 等信息，则不能自行加入 Listing 图片文字或产品卖点。

---

## 🧠 设计理念

Listing Generator 不以“随机生成一张好看的商品图”为目标，而是尝试把 AI 电商视觉工作拆解为：

```text
产品是什么？
      ↓
用户为什么购买？
      ↓
核心卖点是什么？
      ↓
卖点应该如何视觉化？
      ↓
这张图片在 Listing 中承担什么任务？
      ↓
应该使用什么视觉模板？
      ↓
如何保持整套图片视觉统一？
      ↓
如何生成并检查最终图片？
```

最终形成一套从**产品信息 → 电商策略 → 视觉规划 → AI 生图**的完整工作流。

---

## 📄 License

请根据项目实际使用的上游代码、模板及素材情况补充对应 License 信息。
