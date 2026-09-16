# Listing Generator

> 🛒 AI 驱动的 Amazon Listing 视觉生成 Skill  
> 上传产品图片，即可自动完成产品分析、卖点提取、Listing 图片规划、Prompt 生成与 AI 生图。

Listing Generator 是一个面向跨境电商场景的 AI Listing 视觉生成工具。

用户只需要提供产品图片和简单的产品信息，AI 即可分析产品特征与核心卖点，
自动规划 Amazon Listing 图片结构，并生成统一视觉风格的商品主图、卖点图、
场景图及详情页视觉素材。

---

## ✨ 项目特点

### 🧠 自动分析产品

根据产品图片和用户提供的信息自动识别：

- 产品类型
- 外观与材质
- 产品特征
- 核心卖点
- 目标用户
- 使用场景

同时对产品信息进行可信度判断，将信息区分为：

- Confirmed
- Inferred
- Unknown

避免 AI 随意生成不存在的产品参数或卖点。

---

### 🎯 自动提取产品卖点

根据产品信息提取核心 Selling Points，并将卖点转换为：

**Feature → Customer Benefit → Visual Proof**

让产品卖点可以直接转化为 Listing 图片中的视觉表达。

---

### 🖼 自动规划 Amazon Listing 图片

针对 Amazon Listing 场景，自动规划完整图片结构。

默认包括：

| 图片 | 作用 |
|------|------|
| H1 | Hero / Product 主图 |
| H2 | Core Benefit 核心卖点 |
| H3 | Lifestyle / Usage 使用场景 |
| H4 | Comparison / Differentiation 对比差异 |
| H5 | Detail / Secondary Benefit 产品细节 |

如果需要完整 PDP / A+ 页面，还可以继续规划：

D1 Problem / Need  
D2 Solution  
D3 Product Mechanism  
D4 Core Benefits  
D5 How to Use  
D6 Usage Scenarios  
D7 Comparison  
D8 Trust / Quality  
D9 FAQ / CTA

---

## 🎨 25 类电商视觉模板

项目内置 25 类电商视觉模板，包括：

- Hero Image
- Lifestyle Scene
- Flat Lay
- Detail Macro
- Poster Banner
- Social Media
- UGC Style
- Model Showcase
- Before / After
- Packaging
- Infographic
- Creative Concept
- Size / Specification
- Multi Product
- Livestream
- Virtual Try-on
- Exploded View
- Ghost Mannequin
- Multi-angle Grid
- Magazine Editorial
- Seasonal Campaign
- Luxury Atmospherics
- Device Mockup
- Storefront
- Sports Campaign

AI 会根据产品类型、核心卖点、图片用途以及购买驱动力，
自动选择更适合当前产品的视觉模板。

---

## 🎨 Campaign Style Lock

为了避免 AI 批量生图时出现：

- 产品颜色变化
- 字体不统一
- 光线不同
- 背景风格混乱
- 产品比例变化

项目加入了 Campaign Style Lock。

生成整套 Listing 图片前，会统一定义：

- Color Palette
- Typography
- Background
- Lighting
- Layout
- Product Presentation
- Whitespace
- Visual Direction

让整套 Listing 图片保持统一的品牌视觉风格。

---

## ⚙️ 工作流程

```text
Product Image
      ↓
Product Analysis
      ↓
Evidence / Claim Gate
      ↓
Selling Point Extraction
      ↓
Conversion Driver Diagnosis
      ↓
Listing Image Planning
      ↓
Template Selection
      ↓
Campaign Style Lock
      ↓
Prompt Generation
      ↓
Prompt QA
      ↓
Image Generation
      ↓
Image QA
      ↓
Final Listing Images
