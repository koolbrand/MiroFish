<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <BrandLogo class="nav-brand" />
      <div class="nav-links">
        <AppVersion />
        <LanguageSwitcher />
        <router-link to="/projects" class="github-link">
          {{ $t('nav.projects') }} <span class="arrow">→</span>
        </router-link>
        <a href="https://github.com/koolbrand/MiroFish" target="_blank" class="github-link">
          {{ $t('nav.visitGithub') }} <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">{{ $t('home.tagline') }}</span>
            <span class="version-text">{{ $t('home.version') }}</span>
          </div>
          
          <h1 class="main-title">
            {{ $t('home.heroTitle1') }}<br>
            <span class="gradient-text">{{ $t('home.heroTitle2') }}</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              <i18n-t keypath="home.heroDesc" tag="span">
                <template #brand><span class="highlight-bold">{{ $t('home.heroDescBrand') }}</span></template>
                <template #agentScale><span class="highlight-orange">{{ $t('home.heroDescAgentScale') }}</span></template>
                <template #optimalSolution><span class="highlight-code">{{ $t('home.heroDescOptimalSolution') }}</span></template>
              </i18n-t>
            </p>
            <p class="slogan-text">
              {{ $t('home.slogan') }}<span class="blinking-cursor">_</span>
            </p>
          </div>
           
          <div class="decoration-square"></div>
        </div>
        
        <div class="hero-right">
          <!-- D3 force-directed graph — same style as in-app graph -->
          <div class="agent-vis-panel">
            <div class="vis-top-bar">
              <span class="vis-label">SIMULATION ENGINE</span>
              <span class="vis-live"><span class="live-dot"></span>ACTIVE</span>
            </div>
            <div class="vis-svg-wrap">
              <svg ref="simSvg" class="sim-svg"></svg>
              <div class="sim-brand-overlay">
                <BrandLogo class="sim-logo" />
                <div class="sim-brand-sub">by <strong>KOOLBRAND</strong></div>
              </div>
            </div>
            <div class="vis-bottom-bar">
              <div class="vis-stat-row">
                <div class="vis-stat"><span class="stat-val">1,000+</span><span class="stat-lbl">agentes</span></div>
                <div class="vis-stat"><span class="stat-val">5</span><span class="stat-lbl">pasos</span></div>
                <div class="vis-stat"><span class="stat-val">∞</span><span class="stat-lbl">escenarios</span></div>
              </div>
            </div>
          </div>

          <button class="scroll-down-btn" @click="scrollToBottom">↓</button>
        </div>
      </section>

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> {{ $t('home.systemStatus') }}
          </div>
          
          <h2 class="section-title">{{ $t('home.systemReady') }}</h2>
          <p class="section-desc">
            {{ $t('home.systemReadyDesc') }}
          </p>
          
          <!-- 数据指标卡片 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricLowCost') }}</div>
              <div class="metric-label">{{ $t('home.metricLowCostDesc') }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricHighAvail') }}</div>
              <div class="metric-label">{{ $t('home.metricHighAvailDesc') }}</div>
            </div>
          </div>

          <!-- 项目模拟步骤介绍 (新增区域) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> {{ $t('home.workflowSequence') }}
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step01Title') }}</div>
                  <div class="step-desc">{{ $t('home.step01Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step02Title') }}</div>
                  <div class="step-desc">{{ $t('home.step02Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step03Title') }}</div>
                  <div class="step-desc">{{ $t('home.step03Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step04Title') }}</div>
                  <div class="step-desc">{{ $t('home.step04Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step05Title') }}</div>
                  <div class="step-desc">{{ $t('home.step05Desc') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：交互控制台 -->
        <div class="right-panel">
          <div class="console-box">
            <!-- 上传区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.realitySeed') }}</span>
                <span class="console-meta">{{ $t('home.supportedFormats') }}</span>
              </div>
              
              <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt,.png,.jpg,.jpeg,.webp,.gif"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">{{ $t('home.dragToUpload') }}</div>
                  <div class="upload-hint">{{ $t('home.orBrowse') }}</div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 分割线 -->
            <div class="console-divider">
              <span>{{ $t('home.inputParams') }}</span>
            </div>

            <!-- 项目名称 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.projectName') }}</span>
              </div>
              <div class="name-wrapper">
                <input
                  v-model="formData.projectName"
                  type="text"
                  class="name-input"
                  :placeholder="$t('home.projectNamePlaceholder')"
                  maxlength="120"
                  :disabled="loading"
                />
              </div>
            </div>

            <!-- 输入区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.simulationPrompt') }}</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  :placeholder="$t('home.promptPlaceholder')"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">{{ $t('home.engineBadge') }}</div>
              </div>
            </div>

            <!-- 启动按钮 -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">{{ $t('home.startEngine') }}</span>
                <span v-else>{{ $t('home.initializing') }}</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 历史项目数据库 -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import AppVersion from '../components/AppVersion.vue'
import BrandLogo from '../components/BrandLogo.vue'

const router = useRouter()

// ── D3 force-directed graph (same style as in-app GraphPanel) ───────────────
const simSvg = ref(null)
let _d3sim = null

// Predefined demo graph — looks like a real simulation output
const DEMO_NODES = [
  { id: 'n1',  name: 'KoolBrand',  type: 'Brand' },
  { id: 'n2',  name: 'BrandMind',  type: 'Product' },
  { id: 'n3',  name: 'AI',         type: 'Tech' },
  { id: 'n4',  name: 'Marketing',  type: 'Domain' },
  { id: 'n5',  name: 'Startup...',  type: 'Entity' },
  { id: 'n6',  name: 'Canva',      type: 'Competitor' },
  { id: 'n7',  name: 'Designer...', type: 'Agent' },
  { id: 'n8',  name: 'LatAm',      type: 'Market' },
  { id: 'n9',  name: 'Social m...',type: 'Platform' },
  { id: 'n10', name: 'PIX',        type: 'Entity' },
  { id: 'n11', name: 'Carlos R...', type: 'Agent' },
  { id: 'n12', name: 'SaaS Ent...',type: 'Segment' },
  { id: 'n13', name: 'r/Entrep...', type: 'Community' },
  { id: 'n14', name: 'Colombia',   type: 'Location' },
  { id: 'n15', name: 'Freelanc...', type: 'Agent' },
  { id: 'n16', name: 'Angel in...',type: 'Investor' },
  { id: 'n17', name: 'Maria Lo...', type: 'Agent' },
  { id: 'n18', name: 'Traditio...', type: 'Competitor' },
]
const DEMO_EDGES = [
  { source: 'n1', target: 'n2', label: 'Owns' },
  { source: 'n1', target: 'n3', label: 'Uses' },
  { source: 'n2', target: 'n3', label: 'Powered by' },
  { source: 'n2', target: 'n6', label: 'Has competitor' },
  { source: 'n2', target: 'n9', label: 'Targets' },
  { source: 'n2', target: 'n12', label: 'Serves' },
  { source: 'n2', target: 'n13', label: 'Discussed in' },
  { source: 'n4', target: 'n1', label: 'Supports' },
  { source: 'n5', target: 'n2', label: 'Evaluates' },
  { source: 'n7', target: 'n2', label: 'Reviews' },
  { source: 'n8', target: 'n1', label: 'Is market of' },
  { source: 'n10', target: 'n2', label: 'Integrates' },
  { source: 'n11', target: 'n2', label: 'Advocates' },
  { source: 'n14', target: 'n1', label: 'Located in' },
  { source: 'n15', target: 'n7', label: 'Works with' },
  { source: 'n16', target: 'n5', label: 'Funds' },
  { source: 'n17', target: 'n2', label: 'Promotes' },
  { source: 'n18', target: 'n2', label: 'Competes' },
  { source: 'n3', target: 'n5', label: 'Enables' },
]
const DEMO_COLOR_MAP = {
  Brand: '#FF6B35', Product: '#FF4500', Tech: '#E9724C',
  Domain: '#004E89', Entity: '#7B2D8E', Competitor: '#C5283D',
  Agent: '#3498db', Market: '#1A936F', Platform: '#9b59b6',
  Segment: '#27ae60', Community: '#f39c12', Location: '#0D9488',
  Investor: '#e74c3c',
}
const getNodeColor = (type) => DEMO_COLOR_MAP[type] || '#999'

const initNetworkSvg = () => {
  const el = simSvg.value
  if (!el) return

  const W = el.clientWidth || 500
  const H = el.clientHeight || 310

  const svg = d3.select(el)
    .attr('width', W).attr('height', H)
    .attr('viewBox', `0 0 ${W} ${H}`)

  svg.selectAll('*').remove()

  // Deep-copy nodes so D3 can mutate them freely
  const nodes = DEMO_NODES.map(n => ({ ...n }))
  const edges = DEMO_EDGES.map(e => ({ ...e }))

  const sim = d3.forceSimulation(nodes)
    .force('link',    d3.forceLink(edges).id(d => d.id).distance(110))
    .force('charge',  d3.forceManyBody().strength(-320))
    .force('center',  d3.forceCenter(W / 2, H / 2))
    .force('collide', d3.forceCollide(40))
    .force('x',       d3.forceX(W / 2).strength(0.05))
    .force('y',       d3.forceY(H / 2).strength(0.05))
    .alphaDecay(0)         // run forever — gentle continuous drift
    .velocityDecay(0.45)

  _d3sim = sim

  const g = svg.append('g')

  // Edges
  const link = g.append('g').selectAll('line')
    .data(edges).enter().append('line')
    .attr('stroke', '#C0C0C0')
    .attr('stroke-width', 1.5)

  // Edge labels
  const linkLabel = g.append('g').selectAll('text')
    .data(edges).enter().append('text')
    .text(d => d.label)
    .attr('font-size', '8px')
    .attr('fill', '#999')
    .attr('text-anchor', 'middle')
    .style('font-family', 'system-ui, sans-serif')
    .style('pointer-events', 'none')

  // Nodes
  const node = g.append('g').selectAll('circle')
    .data(nodes).enter().append('circle')
    .attr('r', 10)
    .attr('fill', d => getNodeColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2.5)

  // Node labels
  const nodeLabel = g.append('g').selectAll('text')
    .data(nodes).enter().append('text')
    .text(d => d.name)
    .attr('font-size', '11px')
    .attr('fill', '#333')
    .attr('font-weight', '500')
    .attr('dx', 14).attr('dy', 4)
    .style('font-family', 'system-ui, sans-serif')
    .style('pointer-events', 'none')

  sim.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y)

    linkLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2)

    node.attr('cx', d => d.x).attr('cy', d => d.y)
    nodeLabel.attr('x', d => d.x).attr('y', d => d.y)
  })
}

onMounted(async () => {
  await nextTick()
  initNetworkSvg()
})

onUnmounted(() => {
  if (_d3sim) _d3sim.stop()
})
// ────────────────────────────────────────────────────────────────────────────

// 表单数据
const formData = ref({
  simulationRequirement: '',
  projectName: ''
})

// 文件列表
const files = ref([])

// 状态
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// 文件输入引用
const fileInput = ref(null)

// 计算属性:是否可以提交
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// 触发文件选择
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 添加文件
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt', 'png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)
  })
  files.value.push(...validFiles)
}

// 移除文件
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// 滚动到底部
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// 开始模拟 - 立即跳转，API调用在Process页面进行
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  // 存储待上传的数据
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(
      files.value,
      formData.value.simulationRequirement,
      (formData.value.projectName || '').trim()
    )

    // 立即跳转到Process页面（使用特殊标识表示新建项目）
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* 全局变量与重置 */
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  /* 
    使用 Space Grotesk 作为主要标题字体，JetBrains Mono 作为代码/标签字体
    确保已在 index.html 引入这些 Google Fonts 
  */
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-cn: 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* 顶部导航 */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-size: 24px;
  color: var(--white);
  display: inline-flex;
  align-items: center;
  transition: opacity 0.15s ease;
  cursor: pointer;
}

.nav-brand:hover {
  opacity: 0.7;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 16px;
}

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}

.github-link:hover {
  opacity: 0.8;
}

.arrow {
  font-family: sans-serif;
}

/* 主要内容区 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Hero 区域 */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 80px;
  position: relative;
}

.hero-left {
  flex: 1;
  padding-right: 60px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}

.version-text {
  color: #999;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.main-title {
  font-size: 4.5rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #000000 0%, #444444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.highlight-bold {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.highlight-code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 1px;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: var(--orange);
}

.hero-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: stretch;
}

/* ── D3 graph panel ── */
.agent-vis-panel {
  width: 100%;
  background: #fff;
  border: 1px solid #E5E5E5;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.vis-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  border-bottom: 1px solid #EBEBEB;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  letter-spacing: 1.5px;
  background: #fff;
}

.vis-label { color: #999; font-weight: 600; }

.vis-live {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #FF4500;
  font-weight: 700;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #FF4500;
  animation: pulse-live 1.8s ease-in-out infinite;
}

@keyframes pulse-live {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.35; transform: scale(0.65); }
}

.vis-svg-wrap {
  position: relative;
  height: 310px;
  flex-shrink: 0;
  /* Exact same background as in-app GraphPanel */
  background-color: #FAFAFA;
  background-image: radial-gradient(#D0D0D0 1.5px, transparent 1.5px);
  background-size: 24px 24px;
  overflow: hidden;
}

.sim-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.sim-brand-overlay {
  position: absolute;
  bottom: 14px;
  right: 16px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  pointer-events: none;
  background: rgba(250, 250, 250, 0.85);
  backdrop-filter: blur(4px);
  padding: 8px 12px;
  border: 1px solid #E8E8E8;
}

.sim-logo {
  font-size: 26px;
  color: #000;
}

.sim-brand-sub {
  font-family: var(--font-mono);
  font-size: 0.57rem;
  color: #999;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.sim-brand-sub strong { color: #FF4500; }

.vis-bottom-bar {
  padding: 12px 18px;
  border-top: 1px solid #EBEBEB;
  background: #fff;
}

.vis-stat-row {
  display: flex;
  gap: 28px;
}

.vis-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-val {
  font-family: var(--font-mono);
  font-size: 1.15rem;
  font-weight: 700;
  color: #111;
  line-height: 1;
}

.stat-lbl {
  font-family: var(--font-mono);
  font-size: 0.58rem;
  color: #999;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--orange);
  font-size: 1.2rem;
  transition: all 0.2s;
}

.scroll-down-btn:hover {
  border-color: var(--orange);
}

/* Dashboard 双栏布局 */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* 左侧面板 */
.left-panel {
  flex: 0.8;
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
}

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.metric-card {
  border: 1px solid var(--border);
  padding: 20px 30px;
  min-width: 150px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 0.85rem;
  color: #999;
}

/* 项目模拟步骤介绍 */
.steps-container {
  border: 1px solid var(--border);
  padding: 30px;
  position: relative;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--black);
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
}

/* 右侧交互控制台 */
.right-panel {
  flex: 1.2;
}

.console-box {
  border: 1px solid #CCC; /* 外部实线 */
  padding: 8px; /* 内边距形成双重边框感 */
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.upload-zone {
  border: 1px dashed #CCC;
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #FAFAFA;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: #F0F0F0;
  border-color: #999;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #999;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 8px 12px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #999;
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #BBB;
  letter-spacing: 1px;
}

.name-wrapper {
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.name-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 14px 18px;
  font-family: var(--font-mono);
  font-size: 0.95rem;
  color: var(--black);
  outline: none;
  letter-spacing: 0.5px;
}

.name-input::placeholder {
  color: #AAA;
  font-style: italic;
}

.name-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.input-wrapper {
  position: relative;
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #AAA;
}

.start-engine-btn {
  width: 100%;
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  position: relative;
  overflow: hidden;
}

/* 可点击状态（非禁用） */
.start-engine-btn:not(:disabled) {
  background: var(--black);
  border: 1px solid var(--black);
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  transform: none;
  border: 1px solid #E5E5E5;
}

/* 引导动画：微妙的边框脉冲 */
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }
  
  .hero-section {
    flex-direction: column;
  }
  
  .hero-left {
    padding-right: 0;
    margin-bottom: 40px;
  }

  .hero-right {
    width: 100%;
    align-items: stretch;
  }

  .vis-canvas-wrap {
    height: 240px;
  }
}
</style>

<style>
/* English locale adjustments (unscoped to target html[lang]) */
html[lang="en"] .main-title {
  font-size: 3.5rem;
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: -1px;
}

html[lang="en"] .hero-desc {
  text-align: left;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0;
}

html[lang="en"] .slogan-text {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0;
}

html[lang="en"] .tag-row {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .navbar .nav-links {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Left pane: system status + workflow */
html[lang="en"] .status-section {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .status-section .status-ready {
  font-size: 1.6rem;
}

html[lang="en"] .status-section .metric-value {
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 1.4rem;
}

html[lang="en"] .workflow-list .step-title {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .workflow-list .step-desc {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
  font-size: 0.72rem !important;
  line-height: 1.4 !important;
}

html[lang="en"] .workflow-list {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
