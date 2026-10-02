<template>
  <div class="env-setup-panel">
    <div class="scroll-container">
      <!-- Si la preparación falla: una frase clara arriba; el detalle técnico, plegado (antes solo salía en el registro) -->
      <div v-if="prepareError" class="prepare-error" role="alert">
        <p class="prepare-error-title">{{ $t('step2.prepareErrorTitle') }}</p>
        <p class="prepare-error-text">{{ $t('step2.prepareErrorBody') }}</p>
        <details class="prepare-error-details">
          <summary>{{ $t('main.failDetails') }}</summary>
          <code>{{ prepareError }}</code>
        </details>
      </div>

      <!-- Step 01: 模拟实例 -->
      <div class="step-card" :class="{ 'active': phase === 0, 'completed': phase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">{{ $t('step2.simInstanceInit') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 0" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else class="badge processing">{{ $t('step2.initializing') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">
            {{ $t('step2.simInstanceDesc') }}
          </p>

          <div v-if="simulationId" class="info-card tech-only">
            <div class="info-row">
              <span class="info-label">Project ID</span>
              <span class="info-value mono">{{ projectData?.project_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Graph ID</span>
              <span class="info-value mono">{{ projectData?.graph_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Simulation ID</span>
              <span class="info-value mono">{{ simulationId }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Task ID</span>
              <span class="info-value mono">{{ taskId || $t('step2.asyncTaskDone') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: 生成 Agent 人设 -->
      <div class="step-card" :class="{ 'active': phase === 1, 'completed': phase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">{{ $t('step2.generateAgentPersona') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 1" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 1 && prepareError" class="badge error">{{ $t('common.failed') }}</span>
            <span v-else-if="phase === 1" class="badge processing">{{ prepareProgress }}%</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.generateAgentPersonaDesc') }}
          </p>

          <!-- Público con datos reales (CIS): solo aparece si este servidor tiene el banco -->
          <div v-if="cisEstado.disponible" class="cis-toggle" data-testid="cis-toggle">
            <label class="cis-toggle-row">
              <input type="checkbox" v-model="usarCis" class="cis-check" data-testid="cis-checkbox" />
              <span class="cis-toggle-text">
                <span class="cis-toggle-title">{{ $t('step2.cisToggleTitle') }}</span>
                <span class="cis-toggle-desc">{{ $t('step2.cisToggleDesc') }}</span>
              </span>
            </label>
            <div v-if="cisCambiado" class="cis-changed" role="status">
              <span>{{ $t('step2.cisToggleChanged') }}</span>
              <button type="button" class="cis-regen" @click="regenerarPublico">{{ $t('step2.cisRegenerate') }}</button>
            </div>
          </div>

          <!-- Reparto del público elegido, antes de simular -->
          <div v-if="poblacion" class="cis-reparto" data-testid="cis-reparto">
            <div class="cis-reparto-head">
              <span class="cis-reparto-title">{{ $t('step2.cisRepartoTitle') }}</span>
              <span class="cis-source">{{ cisCita }}</span>
            </div>
            <p class="cis-reparto-sub">{{ $t('step2.cisRepartoSub') }} · {{ $t('step2.cisPeople', { n: poblacion.reparto?.n || 0 }) }}</p>
            <div class="cis-bars">
              <div v-for="grupo in cisGrupos" :key="grupo.key" class="cis-group">
                <span class="cis-group-title">{{ grupo.titulo }}</span>
                <div v-for="fila in grupo.filas" :key="fila.label" class="cis-bar-row">
                  <span class="cis-bar-label">{{ fila.label }}</span>
                  <span class="cis-bar-track"><span class="cis-bar-fill" :style="{ width: Math.min(100, fila.pct) + '%' }"></span></span>
                  <span class="cis-bar-pct">{{ fila.pct }}%</span>
                </div>
              </div>
            </div>
            <p class="cis-filters">{{ cisFiltrosTexto }}</p>
            <p v-if="poblacion.relajado" class="cis-relaxed">{{ $t('step2.cisRelaxed') }}</p>
          </div>

          <!-- Profiles Stats -->
          <div v-if="profiles.length > 0" class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ profiles.length }}</span>
              <span class="stat-label">{{ $t('step2.currentAgentCount') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ expectedTotal || '-' }}</span>
              <span class="stat-label">{{ $t('step2.expectedAgentTotal') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ totalTopicsCount }}</span>
              <span class="stat-label">{{ $t('step2.relatedTopicsCount') }}</span>
            </div>
          </div>

          <!-- Profiles List Preview -->
          <div v-if="profiles.length > 0" class="profiles-preview">
            <div class="preview-header">
              <span class="preview-title">{{ $t('step2.generatedAgentPersonas') }}</span>
              <span class="preview-count">
                {{ filteredProfiles.length }}
                <span v-if="filteredProfiles.length !== profiles.length">/ {{ profiles.length }}</span>
              </span>
            </div>

            <!-- Resumen demográfico (para demos con clientes) -->
            <div class="demographics-summary">
              <div v-if="demographics.genderBreakdown.length" class="demo-chips">
                <button
                  v-for="g in demographics.genderBreakdown"
                  :key="g.label"
                  type="button"
                  class="demo-chip"
                  :class="{ active: filters.gender === g.key }"
                  :aria-pressed="filters.gender === g.key"
                  @click="toggleGenderFilter(g.key)"
                >
                  {{ g.label }} · {{ g.count }}
                </button>
              </div>
              <div v-if="demographics.topProfessions.length" class="demo-chips">
                <button
                  v-for="p in demographics.topProfessions"
                  :key="p"
                  type="button"
                  class="demo-chip subtle"
                  :class="{ active: filters.profession === p }"
                  :aria-pressed="filters.profession === p"
                  @click="toggleProfessionFilter(p)"
                >
                  {{ p }}
                </button>
              </div>
            </div>

            <!-- Barra de búsqueda y orden -->
            <div class="profiles-controls">
              <div class="search-wrapper">
                <span class="search-icon" aria-hidden="true">⌕</span>
                <input
                  v-model="filters.query"
                  type="text"
                  class="profiles-search"
                  :placeholder="$t('step2.searchProfilesPlaceholder')"
                  :aria-label="$t('step2.searchProfilesPlaceholder')"
                />
                <button
                  v-if="filters.query || filters.gender || filters.profession"
                  type="button"
                  class="clear-btn"
                  :title="$t('step2.clearFilters')"
                  :aria-label="$t('step2.clearFilters')"
                  @click="clearFilters"
                >×</button>
              </div>
              <select v-model="filters.sort" class="profiles-sort" :aria-label="$t('step2.sortLabel')">
                <option value="default">{{ $t('step2.sortDefault') }}</option>
                <option value="name">{{ $t('step2.sortByName') }}</option>
                <option value="profession">{{ $t('step2.sortByProfession') }}</option>
                <option value="random">{{ $t('step2.sortRandom') }}</option>
              </select>
            </div>

            <div v-if="filteredProfiles.length === 0" class="profiles-empty">
              {{ $t('step2.noProfilesMatch') }}
            </div>

            <div v-else class="profiles-list">
              <div
                v-for="profile in filteredProfiles"
                :key="profile._idx"
                class="profile-card"
                role="button"
                tabindex="0"
                @click="selectProfile(profile)"
                @keydown.enter.prevent="selectProfile(profile)"
                @keydown.space.prevent="selectProfile(profile)"
              >
                <div class="profile-header">
                  <span class="profile-realname">{{ profile.username || $t('common.unknown') }}</span>
                  <span class="profile-username">@{{ profile.name || `agent_${profile._idx}` }}</span>
                </div>
                <div class="profile-meta">
                  <span class="profile-profession">{{ profile.profession || $t('step2.unknownProfession') }}</span>
                  <span v-if="profile.data_source" class="cis-tag" data-testid="cis-tag">{{ $t('step2.cisTag', { ref: profile.data_ref }) }}</span>
                </div>
                <MiniMarkdown v-if="profile.bio" tag="p" inline class="profile-bio" :text="profile.bio" />
                <p v-else class="profile-bio">{{ $t('step2.noBio') }}</p>
                <div v-if="profile.interested_topics?.length" class="profile-topics">
                  <span
                    v-for="topic in profile.interested_topics.slice(0, 3)"
                    :key="topic"
                    class="topic-tag"
                  >{{ topic }}</span>
                  <span v-if="profile.interested_topics.length > 3" class="topic-more">
                    +{{ profile.interested_topics.length - 3 }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: 生成双平台模拟配置 -->
      <div class="step-card" :class="{ 'active': phase === 2, 'completed': phase > 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">{{ $t('step2.dualPlatformConfig') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 2" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 2" class="badge processing">{{ $t('step2.generating') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.dualPlatformConfigDesc') }}
          </p>
          
          <!-- Config Preview -->
          <div v-if="simulationConfig" class="config-detail-panel">
            <!-- 时间配置 -->
            <div class="config-block">
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.simulationDuration') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.total_simulation_hours || '-' }} {{ $t('common.hours') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.roundDuration') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.minutes_per_round || '-' }} {{ $t('common.minutes') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.totalRounds') }}</span>
                  <span class="config-item-value">{{ Math.floor((simulationConfig.time_config?.total_simulation_hours * 60 / simulationConfig.time_config?.minutes_per_round)) || '-' }} {{ $t('common.rounds') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.activePerHour') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.agents_per_hour_min }}-{{ simulationConfig.time_config?.agents_per_hour_max }}</span>
                </div>
              </div>
              <div class="time-periods">
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.peakHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.peak_hours?.join(':00, ') }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.peak_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.workHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.work_hours?.[0] }}:00-{{ simulationConfig.time_config?.work_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.work_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.morningHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.morning_hours?.[0] }}:00-{{ simulationConfig.time_config?.morning_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.morning_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.offPeakHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.off_peak_hours?.[0] }}:00-{{ simulationConfig.time_config?.off_peak_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.off_peak_activity_multiplier }}</span>
                </div>
              </div>
            </div>

            <!-- Agent 配置 -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">{{ $t('step2.agentConfig') }}</span>
                <span class="config-block-badge">{{ simulationConfig.agent_configs?.length || 0 }} {{ $t('common.items') }}</span>
              </div>
              <div class="agents-cards">
                <div 
                  v-for="agent in visibleAgentConfigs" 
                  :key="agent.agent_id" 
                  class="agent-card"
                >
                  <!-- 卡片头部 -->
                  <div class="agent-card-header">
                    <div class="agent-identity">
                      <span class="agent-id">{{ $t('step2.agentNumber', { id: agent.agent_id }) }}</span>
                      <span class="agent-name">{{ agent.entity_name }}</span>
                    </div>
                    <div class="agent-tags">
                      <span class="agent-type" :title="agent.entity_type">{{ entityLabel(agent.entity_type) }}</span>
                      <span class="agent-stance" :class="'stance-' + agent.stance">{{ stanceLabel(agent.stance) }}</span>
                    </div>
                  </div>
                  
                  <!-- 活跃时间轴 -->
                  <div class="agent-timeline">
                    <span class="timeline-label">{{ $t('step2.activeTimePeriod') }}</span>
                    <div class="mini-timeline">
                      <div 
                        v-for="hour in 24" 
                        :key="hour - 1" 
                        class="timeline-hour"
                        :class="{ 'active': agent.active_hours?.includes(hour - 1) }"
                        :title="`${hour - 1}:00`"
                      ></div>
                    </div>
                    <div class="timeline-marks">
                      <span>0</span>
                      <span>6</span>
                      <span>12</span>
                      <span>18</span>
                      <span>24</span>
                    </div>
                  </div>

                  <!-- 行为参数 -->
                  <div class="agent-params">
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.postsPerHour') }}</span>
                        <span class="param-value">{{ agent.posts_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.commentsPerHour') }}</span>
                        <span class="param-value">{{ agent.comments_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.responseDelay') }}</span>
                        <span class="param-value">{{ agent.response_delay_min }}-{{ agent.response_delay_max }}min</span>
                      </div>
                    </div>
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.activityLevel') }}</span>
                        <span class="param-value with-bar">
                          <span class="mini-bar" :style="{ width: (agent.activity_level * 100) + '%' }"></span>
                          {{ (agent.activity_level * 100).toFixed(0) }}%
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.sentimentBias') }}</span>
                        <span class="param-value" :class="agent.sentiment_bias > 0 ? 'positive' : agent.sentiment_bias < 0 ? 'negative' : 'neutral'">
                          {{ agent.sentiment_bias > 0 ? '+' : '' }}{{ agent.sentiment_bias?.toFixed(1) }}
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.influenceWeight') }}</span>
                        <span class="param-value highlight">{{ agent.influence_weight?.toFixed(1) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <button
                v-if="(simulationConfig.agent_configs?.length || 0) > AGENTS_PREVIEW"
                type="button"
                class="agents-more"
                @click="showAllAgents = !showAllAgents"
              >
                {{ showAllAgents ? $t('ui.agentsShowLess') : $t('ui.agentsShowAll', { count: simulationConfig.agent_configs.length }) }}
              </button>
            </div>

            <!-- 平台配置 -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">{{ $t('step2.recommendAlgoConfig') }}</span>
              </div>
              <div class="platforms-grid">
                <div v-if="simulationConfig.twitter_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">{{ $t('step2.platform1Name') }}</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.recencyWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.popularityWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.relevanceWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.viralThreshold') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.echoChamberStrength') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="simulationConfig.reddit_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">{{ $t('step2.platform2Name') }}</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.recencyWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.popularityWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.relevanceWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.viralThreshold') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.echoChamberStrength') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- LLM 配置推理 -->
            <div v-if="simulationConfig.generation_reasoning" class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">{{ $t('step2.llmConfigReasoning') }}</span>
              </div>
              <div class="reasoning-content">
                <!-- El texto lo escribe el modelo: se parte en título + párrafos + listas (datos, nunca HTML) -->
                <div v-for="(section, idx) in reasoningBlocks" :key="idx" class="reasoning-item">
                  <h4 v-if="section.label" class="reasoning-label">{{ section.label }}</h4>
                  <template v-for="(block, i) in section.blocks" :key="i">
                    <p v-if="block.type === 'p'" class="reasoning-text">{{ block.text }}</p>
                    <ul v-else class="reasoning-list">
                      <li v-for="(item, j) in block.items" :key="j">{{ item }}</li>
                    </ul>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 04: 初始激活编排 -->
      <div class="step-card" :class="{ 'active': phase === 3, 'completed': phase > 3 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">04</span>
            <span class="step-title">{{ $t('step2.initialActivation') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 3" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 3" class="badge processing">{{ $t('step2.orchestrating') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.initialActivationDesc') }}
          </p>

          <div v-if="simulationConfig?.event_config" class="orchestration-content">
            <!-- 叙事方向 -->
            <div class="narrative-box">
              <span class="box-label narrative-label">
                <!-- brújula en tinta (antes, degradado naranja ajeno a la marca) -->
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="special-icon" aria-hidden="true">
                  <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M16.24 7.76L14.12 14.12L7.76 16.24L9.88 9.88L16.24 7.76Z" fill="var(--kb-accent-solid)" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                {{ $t('step2.narrativeDirection') }}
              </span>
              <MiniMarkdown class="narrative-text" :text="simulationConfig.event_config.narrative_direction" />
            </div>

            <!-- 热点话题 -->
            <div class="topics-section">
              <span class="box-label">{{ $t('step2.initialHotTopics') }}</span>
              <div class="hot-topics-grid">
                <span v-for="topic in simulationConfig.event_config.hot_topics" :key="topic" class="hot-topic-tag">
                  # {{ topic }}
                </span>
              </div>
            </div>

            <!-- 初始帖子流 -->
            <div class="initial-posts-section">
              <span class="box-label">{{ $t('step2.initialActivationSeq', { count: simulationConfig.event_config.initial_posts.length }) }}</span>
              <div class="posts-timeline">
                <div v-for="(post, idx) in simulationConfig.event_config.initial_posts" :key="idx" class="timeline-item">
                  <div class="timeline-marker"></div>
                  <div class="timeline-content">
                    <div class="post-header">
                      <span class="post-role">{{ post.poster_type }}</span>
                      <span class="post-agent-info">
                        <span class="post-id">{{ $t('step2.agentNumber', { id: post.poster_agent_id }) }}</span>
                        <span class="post-username">@{{ getAgentUsername(post.poster_agent_id) }}</span>
                      </span>
                    </div>
                    <MiniMarkdown class="post-text" :text="post.content" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 05: 准备完成 -->
      <div class="step-card" :class="{ 'active': phase === 4 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">05</span>
            <span class="step-title">{{ $t('step2.setupComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase >= 4 && alreadyRun" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase >= 4" class="badge processing">{{ $t('step1.inProgress') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/start</p>
          <p class="description">{{ $t('step2.setupCompleteDesc') }}</p>
          
          <!-- 模拟轮数配置 - 只有在配置生成完成且轮数计算出来后才显示 -->
          <div v-if="simulationConfig && autoGeneratedRounds && !alreadyRun && !autoRunning" class="rounds-config-section" ref="roundsSection">
            <div class="rounds-header">
              <div class="header-left">
                <span class="section-title">{{ $t('step2.roundsConfig') }}</span>
                <span class="section-desc">{{ $t('step2.roundsConfigDesc', { hours: simulationConfig?.time_config?.total_simulation_hours || '-', minutesPerRound: simulationConfig?.time_config?.minutes_per_round || '-' }) }}</span>
              </div>
              <label class="switch-control">
                <input type="checkbox" class="switch-input" v-model="useCustomRounds">
                <span class="switch-track" aria-hidden="true"></span>
                <span class="switch-label">{{ $t('step2.customToggle') }}</span>
              </label>
            </div>
            
            <Transition name="fade" mode="out-in">
              <div v-if="useCustomRounds" class="rounds-content custom" key="custom">
                <div class="slider-display">
                  <div class="slider-main-value">
                    <span class="val-num">{{ customMaxRounds }}</span>
                    <span class="val-unit">{{ $t('step2.roundsUnit') }}</span>
                  </div>
                  <div class="slider-meta-info">
                    <span>{{ $t('step2.estimatedDuration', { minutes: roundsMinutes(customMaxRounds) }) }}</span>
                  </div>
                </div>

                <div class="range-wrapper">
                  <input 
                    type="range" 
                    v-model.number="customMaxRounds" 
                    min="10" 
                    :max="sliderMaxRounds"
                    step="5"
                    class="minimal-slider"
                    :style="{ '--percent': ((customMaxRounds - 10) / (sliderMaxRounds - 10)) * 100 + '%' }"
                  />
                  <div class="range-marks">
                    <span>10</span>
                    <button
                      type="button"
                      class="mark-recommend"
                      :class="{ active: customMaxRounds === 40 }"
                      @click="customMaxRounds = 40"
                      :style="{ position: 'absolute', left: `calc(${(40 - 10) / (sliderMaxRounds - 10) * 100}% - 30px)` }"
                    >{{ $t('step2.recommendedRounds', { rounds: 40 }) }}</button>
                    <span>{{ sliderMaxRounds }}</span>
                  </div>
                </div>
              </div>
              
              <div v-else class="rounds-content auto" key="auto">
                <div class="auto-info-card">
                  <div class="auto-value">
                    <span class="val-num">{{ serverRounds }}</span>
                    <span class="val-unit">{{ $t('step2.roundsUnit') }}</span>
                  </div>
                  <div class="auto-content">
                    <div class="auto-meta-row">
                      <span class="duration-badge">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                          <circle cx="12" cy="12" r="10"></circle>
                          <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        {{ $t('step2.estimatedDurationFull', { minutes: roundsMinutes(serverRounds) }) }}
                      </span>
                    </div>
                    <div class="auto-desc">
                      <button type="button" class="highlight-tip" @click="useCustomRounds = true">{{ $t('step2.customTip') }} ➝</button>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Modo lectura: ya se ejecutó (se consulta, no se vuelve a lanzar) o la lanza el automático -->
          <p v-if="alreadyRun" class="ro-note">{{ $t('step2.readOnlyNote', { rounds: runTotalRounds || '—' }) }}</p>
          <p v-else-if="autoRunning" class="ro-note">{{ $t('auto.step2Note') }}</p>
          <div class="action-group dual" data-tour="env-start-sim">
            <button
              class="action-btn secondary"
              @click="$emit('go-back')"
            >
              ← {{ $t('step2.backToGraphBuild') }}
            </button>
            <!-- Con la barra fija a la vista, su botón es el único relleno; este repite la acción en contorno -->
            <button
              v-if="alreadyRun"
              class="action-btn"
              :class="hasActionBar ? 'outline' : 'primary'"
              @click="openRun"
            >
              {{ $t('step2.viewSimulation') }} ➝
            </button>
            <button
              v-else-if="!autoRunning"
              class="action-btn"
              :class="hasActionBar ? 'outline' : 'primary'"
              :disabled="phase < 4"
              @click="handleStartSimulation"
            >
              {{ $t('step2.startDualWorldSim') }} ➝
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Barra de acción fija: siempre a la vista cuando la preparación termina -->
    <div v-if="phase >= 4 && alreadyRun" class="step2-action-bar">
      <div class="action-bar-rounds">
        <span class="action-bar-label">{{ $t('ui.roundsLabel') }}</span>
        <strong>{{ runTotalRounds || '—' }}</strong>
      </div>
      <button class="action-btn primary action-bar-start" @click="openRun">
        {{ $t('step2.viewSimulation') }} →
      </button>
    </div>
    <div v-else-if="phase >= 4 && !autoRunning" class="step2-action-bar">
      <div class="action-bar-rounds">
        <span class="action-bar-label">{{ $t('ui.roundsLabel') }}</span>
        <strong>{{ useCustomRounds ? customMaxRounds : serverRounds }}</strong>
        <button type="button" class="action-bar-adjust" @click="scrollToRounds">{{ $t('ui.adjust') }}</button>
      </div>
      <button class="action-btn primary action-bar-start" @click="handleStartSimulation">
        {{ $t('step2.startDualWorldSim') }} →
      </button>
    </div>

    <!-- Profile Detail Modal -->
    <Transition name="modal">
      <div v-if="selectedProfile" class="profile-modal-overlay" @click.self="selectedProfile = null">
        <div class="profile-modal" role="dialog" aria-modal="true" :aria-label="selectedProfile.username || selectedProfile.name">
          <div class="modal-header">
          <div class="modal-header-info">
            <div class="modal-name-row">
              <span class="modal-realname">{{ selectedProfile.username }}</span>
              <span class="modal-username">@{{ selectedProfile.name }}</span>
            </div>
            <span class="modal-profession">{{ selectedProfile.profession }}</span>
          </div>
          <button type="button" class="close-btn" :aria-label="$t('common.close')" :title="$t('common.close')" @click="selectedProfile = null">×</button>
        </div>
        
        <div class="modal-body">
          <!-- 基本信息 -->
          <div class="modal-info-grid">
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalAge') }}</span>
              <span class="info-value">{{ selectedProfile.age || '-' }} {{ $t('step2.yearsOld') }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalGender') }}</span>
              <span class="info-value">{{ { male: $t('step2.genderMale'), female: $t('step2.genderFemale'), other: $t('step2.genderOther') }[selectedProfile.gender] || selectedProfile.gender }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalCountry') }}</span>
              <span class="info-value">{{ selectedProfile.country || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalMbti') }}</span>
              <span class="info-value mbti">{{ selectedProfile.mbti || '-' }}</span>
            </div>
          </div>

          <div v-if="selectedProfile.data_source" class="modal-section cis-modal">
            <span class="cis-tag">{{ $t('step2.cisSource', { ref: selectedProfile.data_ref }) }}</span>
            <template v-if="selectedProfile.memory_facts?.length">
              <span class="section-label">{{ $t('step2.cisMemoryTitle') }}</span>
              <ul class="cis-facts">
                <li v-for="(h, i) in selectedProfile.memory_facts" :key="i">{{ h }}</li>
              </ul>
            </template>
          </div>

          <!-- 简介 -->
          <div class="modal-section">
            <span class="section-label">{{ $t('step2.profileModalBio') }}</span>
            <MiniMarkdown v-if="selectedProfile.bio" class="section-bio" :text="selectedProfile.bio" />
            <p v-else class="section-bio">{{ $t('step2.noBio') }}</p>
          </div>

          <!-- 关注话题 -->
          <div class="modal-section" v-if="selectedProfile.interested_topics?.length">
            <span class="section-label">{{ $t('step2.profileModalTopics') }}</span>
            <div class="topics-grid">
              <span 
                v-for="topic in selectedProfile.interested_topics" 
                :key="topic" 
                class="topic-item"
              >{{ topic }}</span>
            </div>
          </div>

          <!-- 详细人设 -->
          <div class="modal-section" v-if="selectedProfile.persona">
            <span class="section-label">{{ $t('step2.profileModalPersona') }}</span>
            
            <!-- 人设维度概览 -->
            <div class="persona-dimensions">
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimExperience') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimExperienceDesc') }}</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimBehavior') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimBehaviorDesc') }}</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimMemory') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimMemoryDesc') }}</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimSocial') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimSocialDesc') }}</span>
              </div>
            </div>

            <div class="persona-content">
              <MiniMarkdown class="section-persona" :text="selectedProfile.persona" />
            </div>
          </div>
        </div>
      </div>
      </div>
    </Transition>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">{{ $t('ui.systemDashboard') }}</span>
        <span v-if="!showTech && lastLog" class="log-last">{{ lastLog }}</span>
        <button type="button" class="log-toggle" @click="toggleTech">{{ showTech ? $t('ui.hideLog') : $t('ui.showLog') }}</button>
        <span class="log-id tech-only">{{ simulationId || 'NO_SIMULATION' }}</span>
      </div>
      <div class="log-content" ref="logContent" v-show="showTech">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reasoningSections } from '../lib/reasoningText'
import { useTechDetails } from '../composables/useTechDetails'
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  prepareSimulation,
  getPrepareStatus,
  getSimulationProfilesRealtime,
  getSimulationConfig,
  getSimulationConfigRealtime,
  getSimulation,
  getRunStatus,
  getPoblacionEstado,
  getPoblacionSimulacion
} from '../api/simulation'
import { usePipeline } from '../composables/usePipeline'
import { MiniMarkdown } from '../lib/miniMarkdown'
import { MANUAL_MAX_ROUNDS, SERVER_MAX_ROUNDS, roundsMinutes, rememberedRounds } from '../lib/rounds'
import { entityLabel } from '../lib/typeLabels'

const { t, te } = useI18n()

const props = defineProps({
  simulationId: String,  // 从父组件传入
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})
const { showTech, toggleTech } = useTechDetails()
const lastLog = computed(() => {
  const logs = props.systemLogs || []
  const last = logs[logs.length - 1]
  return last ? String(last.msg || '') : ''
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

// Modo lectura: una simulación que ya se ejecutó se consulta aquí, no se vuelve a configurar ni a lanzar
const runnerStatus = ref(null)
const runTotalRounds = ref(null)
const alreadyRun = computed(() => !!runnerStatus.value && runnerStatus.value !== 'idle')
const { isRunning: autoRunning, state: pipelineState } = usePipeline(() => props.projectData?.project_id)
const loadRunStatus = async () => {
  if (!props.simulationId) return
  try {
    const res = await getRunStatus(props.simulationId)
    runnerStatus.value = res?.data?.runner_status || null
    runTotalRounds.value = res?.data?.total_rounds || null
  } catch (e) {
    runnerStatus.value = null
  }
}
// el automático la lanza: en cuanto pasa a la etapa de simulación, este paso queda en lectura
watch(() => pipelineState.value?.stage_index, (i) => { if (i >= 3) loadRunStatus() })
const openRun = () => emit('next-step', {})

// Error de preparación para la pantalla: frase clara arriba y el texto del servidor plegado como detalle
const prepareError = ref('')
const setPrepareError = (detail, hint) => {
  prepareError.value = [detail || t('common.unknownError'), hint].filter(Boolean).join('\n')
}
// Postura de cada agente traducida (el motor la da en inglés: supportive, opposing, neutral, observer)
const stanceLabel = (s) => (s && te(`step2.stance.${s}`) ? t(`step2.stance.${s}`) : (s || ''))

// State
const phase = ref(0) // 0: 初始化, 1: 生成人设, 2: 生成配置, 3: 完成
const taskId = ref(null)
const prepareProgress = ref(0)
const currentStage = ref('')
const progressMessage = ref('')
const profiles = ref([])
const entityTypes = ref([])
const expectedTotal = ref(null)
const simulationConfig = ref(null)
const selectedProfile = ref(null)
const showProfilesDetail = ref(true)

// 日志去重：记录上一次输出的关键信息
let lastLoggedMessage = ''
let lastLoggedProfileCount = 0
let lastLoggedConfigStage = ''

// 模拟轮数配置
// Personalizado por defecto: la app ya recomienda reducir rondas en las primeras
// pruebas (el automático puede dar 168 y tardar horas).
const useCustomRounds = ref(true)
const customMaxRounds = ref(rememberedRounds() ?? 40)   // lo elegido en la portada; si no, 40
const AGENTS_PREVIEW = 6
const showAllAgents = ref(false)
const roundsSection = ref(null)
const scrollToRounds = () => roundsSection.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
// La barra fija de abajo sale en estos dos casos (mismas condiciones que su v-if)
const hasActionBar = computed(() => phase.value >= 4 && (alreadyRun.value || !autoRunning.value))

// Watch stage to update phase
watch(currentStage, (newStage) => {
  if (newStage === '生成Agent人设' || newStage === 'generating_profiles') {
    phase.value = 1
  } else if (newStage === '生成模拟配置' || newStage === 'generating_config') {
    phase.value = 2
    // 进入配置生成阶段，开始轮询配置
    if (!configTimer) {
      addLog(t('log.startGeneratingConfig'))
      startConfigPolling()
    }
  } else if (newStage === '准备模拟脚本' || newStage === 'copying_scripts') {
    phase.value = 2 // 仍属于配置阶段
  }
})

// 从配置中计算自动生成的轮数（不使用硬编码默认值）
const visibleAgentConfigs = computed(() => {
  const all = simulationConfig.value?.agent_configs || []
  return showAllAgents.value ? all : all.slice(0, AGENTS_PREVIEW)
})

const autoGeneratedRounds = computed(() => {
  if (!simulationConfig.value?.time_config) {
    return null // 配置未生成时返回 null
  }
  const totalHours = simulationConfig.value.time_config.total_simulation_hours
  const minutesPerRound = simulationConfig.value.time_config.minutes_per_round
  if (!totalHours || !minutesPerRound) {
    return null // 配置数据不完整时返回 null
  }
  const calculatedRounds = Math.floor((totalHours * 60) / minutesPerRound)
  // 确保最大轮数不小于40（推荐值），避免滑动条范围异常
  return Math.max(calculatedRounds, 40)
})

// Lo más que se deja elegir a mano: lo que calcula la configuración, sin pasar de MANUAL_MAX_ROUNDS
const sliderMaxRounds = computed(() => Math.min(autoGeneratedRounds.value || MANUAL_MAX_ROUNDS, MANUAL_MAX_ROUNDS))
// Si se deja la cifra automática, el servidor la recorta a SERVER_MAX_ROUNDS: la pantalla enseña lo que de verdad correrá
const serverRounds = computed(() => Math.min(autoGeneratedRounds.value || 0, SERVER_MAX_ROUNDS))

// Nunca proponer más rondas de las que calcula la propia configuración ni de las que se dejan elegir
watch(sliderMaxRounds, (max) => {
  if (customMaxRounds.value > max) customMaxRounds.value = max
}, { immediate: true })

// Polling timer
let pollTimer = null
let profilesTimer = null
let configTimer = null

// Computed
const displayProfiles = computed(() => {
  if (showProfilesDetail.value) {
    return profiles.value
  }
  return profiles.value.slice(0, 6)
})

// 根据agent_id获取对应的username
const getAgentUsername = (agentId) => {
  if (profiles.value && profiles.value.length > agentId && agentId >= 0) {
    const profile = profiles.value[agentId]
    return profile?.username || `agent_${agentId}`
  }
  return `agent_${agentId}`
}

// 计算所有人设的关联话题总数
const totalTopicsCount = computed(() => {
  return profiles.value.reduce((sum, p) => {
    return sum + (p.interested_topics?.length || 0)
  }, 0)
})

// ─── Agent Explorer: búsqueda, filtros y demografía ──────────────────
const filters = ref({
  query: '',
  gender: null,       // 'male' | 'female' | 'other' | null
  profession: null,   // string | null
  sort: 'default',    // 'default' | 'name' | 'profession' | 'random'
})

// Perfiles con un índice estable para key + orden aleatorio
const indexedProfiles = computed(() => {
  return profiles.value.map((p, idx) => ({ ...p, _idx: idx }))
})

// Resumen demográfico (para mostrar al cliente en demos)
const demographics = computed(() => {
  const genderCounts = { male: 0, female: 0, other: 0 }
  const professionCounts = {}

  for (const p of profiles.value) {
    const g = (p.gender || '').toLowerCase()
    if (g === 'male' || g === 'female') genderCounts[g]++
    else if (g) genderCounts.other++

    const prof = (p.profession || '').trim()
    if (prof) {
      professionCounts[prof] = (professionCounts[prof] || 0) + 1
    }
  }

  const genderBreakdown = [
    { key: 'male', label: t('step2.genderMale'), count: genderCounts.male },
    { key: 'female', label: t('step2.genderFemale'), count: genderCounts.female },
    { key: 'other', label: t('step2.genderOther'), count: genderCounts.other },
  ].filter((g) => g.count > 0)

  const topProfessions = Object.entries(professionCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name]) => name)

  return { genderBreakdown, topProfessions }
})

// Fisher-Yates determinista usando _idx como semilla; cambia al refrescar filtros
let randomSeed = 0
const shuffle = (arr) => {
  const a = arr.slice()
  let seed = randomSeed || 1
  for (let i = a.length - 1; i > 0; i--) {
    seed = (seed * 9301 + 49297) % 233280
    const j = Math.floor((seed / 233280) * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

watch(() => filters.value.sort, (sort) => {
  if (sort === 'random') randomSeed = Date.now()
})

const filteredProfiles = computed(() => {
  const q = filters.value.query.trim().toLowerCase()
  let out = indexedProfiles.value

  if (q) {
    out = out.filter((p) => {
      const hay = [
        p.username,
        p.name,
        p.profession,
        p.country,
        p.bio,
        p.persona,
      ].filter(Boolean).join(' ').toLowerCase()
      return hay.includes(q)
    })
  }

  if (filters.value.gender) {
    out = out.filter((p) => {
      const g = (p.gender || '').toLowerCase()
      if (filters.value.gender === 'other') return g && g !== 'male' && g !== 'female'
      return g === filters.value.gender
    })
  }

  if (filters.value.profession) {
    out = out.filter((p) => (p.profession || '').trim() === filters.value.profession)
  }

  switch (filters.value.sort) {
    case 'name':
      return out.slice().sort((a, b) =>
        (a.username || a.name || '').localeCompare(b.username || b.name || '')
      )
    case 'profession':
      return out.slice().sort((a, b) =>
        (a.profession || '').localeCompare(b.profession || '')
      )
    case 'random':
      return shuffle(out)
    default:
      return out
  }
})

const toggleGenderFilter = (g) => {
  filters.value.gender = filters.value.gender === g ? null : g
}
const toggleProfessionFilter = (p) => {
  filters.value.profession = filters.value.profession === p ? null : p
}
const clearFilters = () => {
  filters.value.query = ''
  filters.value.gender = null
  filters.value.profession = null
}

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// 处理开始模拟按钮点击
const handleStartSimulation = () => {
  if (alreadyRun.value) return openRun()
  if (autoRunning.value) return
  // 构建传递给父组件的参数
  const params = {}
  
  if (useCustomRounds.value) {
    // 用户自定义轮数，传递 max_rounds 参数
    params.maxRounds = customMaxRounds.value
    addLog(t('log.startSimCustomRounds', { rounds: customMaxRounds.value }))
  } else {
    // 用户选择保持自动生成的轮数，不传递 max_rounds 参数
    addLog(t('log.startSimAutoRounds', { rounds: serverRounds.value }))
  }
  
  emit('next-step', params)
}

const truncateBio = (bio) => {
  if (bio.length > 80) {
    return bio.substring(0, 80) + '...'
  }
  return bio
}

const selectProfile = (profile) => {
  selectedProfile.value = profile
}

// 自动开始准备模拟
// Resumen del filtro de Jev: se registra una sola vez por preparación
let entityFilterLogged = false
const logEntityFilter = (summary) => {
  if (entityFilterLogged || !summary || !summary.applied) return
  entityFilterLogged = true
  const audience = Math.round((summary.audience_ratio || 0) * 100)
  addLog(t('log.jevFilterSummary', {
    dropped: (summary.dropped || []).length,
    kept: summary.kept,
    audience
  }))
  if ((summary.dropped || []).length) {
    addLog(t('log.jevFilterDropped', { names: summary.dropped.map(d => d.name).join(', ') }))
  }
  if (summary.audience_expanded) {
    addLog(t('log.jevAudienceExpanded', { count: summary.audience_expanded }))
  }
  if (summary.low_audience) {
    addLog(t('log.jevLowAudience', { audience, minimum: 40 }))
  }
}

// ---- Público con datos reales · España (CIS) ----
const cisEstado = ref({ disponible: false, por_defecto: false, estudios: [] })
const usarCis = ref(false)
const cisUsado = ref(null)          // valor con el que se lanzó la preparación en curso
const poblacion = ref(null)         // resumen de poblacion_cis.json (reparto, filtros, avisos)
const cisCambiado = computed(() => cisEstado.value.disponible && cisUsado.value !== null && usarCis.value !== cisUsado.value)
const cisCita = computed(() => {
  const est = poblacion.value?.estudios || []
  return est.length ? t('step2.cisSource', { ref: est.join(', ') }) : t('step2.cisSourceShort')
})
const cisGrupos = computed(() => {
  const r = poblacion.value?.reparto
  if (!r) return []
  const filas = (obj) => Object.entries(obj || {}).map(([label, pct]) => ({ label, pct }))
  return [
    { key: 'sexo', titulo: t('step2.cisSexo'), filas: filas(r.sexo) },
    { key: 'edad', titulo: t('step2.cisEdad'), filas: filas(r.edad) },
    { key: 'region', titulo: t('step2.cisRegion'), filas: filas(r.region) }
  ].filter(g => g.filas.length)
})
const cisFiltrosTexto = computed(() => {
  const f = poblacion.value?.filtros_aplicados || {}
  const partes = Object.entries(f).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
  return partes.length ? t('step2.cisFilters', { filters: partes.join(' · ') }) : t('step2.cisNoFilters')
})

const cargarPoblacion = async () => {
  if (!props.simulationId || !cisEstado.value.disponible) return
  try {
    const res = await getPoblacionSimulacion(props.simulationId)
    poblacion.value = (res.success && res.data) ? res.data : null
  } catch (e) {
    poblacion.value = null
  }
}

const iniciarEstadoCis = async () => {
  try {
    const res = await getPoblacionEstado()
    if (res.success && res.data) {
      cisEstado.value = res.data
      usarCis.value = !!res.data.por_defecto
    }
  } catch (e) {
    cisEstado.value = { disponible: false, por_defecto: false, estudios: [] }
  }
}

const regenerarPublico = async () => {
  stopPolling()
  stopProfilesPolling()
  profiles.value = []
  poblacion.value = null
  lastLoggedProfileCount = 0
  await startPrepareSimulation(true)
}

const startPrepareSimulation = async (force = false) => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    emit('update-status', 'error')
    return
  }
  
  // 标记第一步完成，开始第二步
  phase.value = 1
  addLog(t('log.simInstanceCreated', { id: props.simulationId }))
  addLog(t('log.preparingSimEnv'))
  emit('update-status', 'processing')
  
  try {
    const peticion = {
      simulation_id: props.simulationId,
      use_llm_for_profiles: true,
      parallel_profile_count: 5
    }
    if (cisEstado.value.disponible) {
      peticion.poblacion_cis = usarCis.value
      cisUsado.value = usarCis.value
    }
    if (force) peticion.force_regenerate = true
    const res = await prepareSimulation(peticion)
    
    if (res.success && res.data) {
      if (res.data.already_prepared) {
        addLog(t('log.detectedExistingPrep'))
        await loadPreparedData()
        return
      }

      taskId.value = res.data.task_id
      addLog(t('log.prepareTaskStarted'))
      addLog(t('log.prepareTaskId', { taskId: res.data.task_id }))

      // 立即设置预期Agent总数（从prepare接口返回值获取）
      if (res.data.expected_entities_count) {
        expectedTotal.value = res.data.expected_entities_count
        addLog(t('log.zepEntitiesFound', { count: res.data.expected_entities_count }))
        if (res.data.entity_types && res.data.entity_types.length > 0) {
          addLog(t('log.entityTypes', { types: res.data.entity_types.join(', ') }))
        }
      }

      addLog(t('log.startPollingProgress'))
      // 开始轮询进度
      startPolling()
      // 开始实时获取 Profiles
      startProfilesPolling()
    } else {
      // Backend rejected /prepare synchronously (most commonly because the
      // graph contained 0 usable entities).  Surface the full error so the
      // user knows exactly what to do instead of seeing an infinite spinner.
      const backendError = res.error || t('common.unknownError')
      const hint = res.data?.hint
      addLog(t('log.prepareFailed', { error: backendError }))
      if (hint) {
        addLog(t('log.prepareFailedHint', { hint }))
      }
      setPrepareError(backendError, hint)
      emit('update-status', 'error')
    }
  } catch (err) {
    addLog(t('log.prepareException', { error: err.message }))
    setPrepareError(err?.response?.data?.error || err.message, err?.response?.data?.data?.hint)
    emit('update-status', 'error')
  }
}

const startPolling = () => {
  pollTimer = setInterval(pollPrepareStatus, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const startProfilesPolling = () => {
  profilesTimer = setInterval(fetchProfilesRealtime, 3000)
}

const stopProfilesPolling = () => {
  if (profilesTimer) {
    clearInterval(profilesTimer)
    profilesTimer = null
  }
}

const pollPrepareStatus = async () => {
  if (!taskId.value && !props.simulationId) return

  // Safety net: watch for simulation-level failure that the task-level
  // status poll may not surface.
  if (await checkSimulationFailed()) return

  try {
    const res = await getPrepareStatus({
      task_id: taskId.value,
      simulation_id: props.simulationId
    })
    
    if (res.success && res.data) {
      const data = res.data
      
      // 更新进度
      prepareProgress.value = data.progress || 0
      progressMessage.value = data.message || ''
      logEntityFilter(data.entity_filter)
      
      // 解析阶段信息并输出详细日志
      if (data.progress_detail) {
        currentStage.value = data.progress_detail.current_stage_name || ''
        
        // 输出详细进度日志（避免重复）
        const detail = data.progress_detail
        const logKey = `${detail.current_stage}-${detail.current_item}-${detail.total_items}`
        if (logKey !== lastLoggedMessage && detail.item_description) {
          lastLoggedMessage = logKey
          const stageInfo = `[${detail.stage_index}/${detail.total_stages}]`
          if (detail.total_items > 0) {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.current_item}/${detail.total_items} - ${detail.item_description}`)
          } else {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.item_description}`)
          }
        }
      } else if (data.message) {
        // 从消息中提取阶段
        const match = data.message.match(/\[(\d+)\/(\d+)\]\s*([^:]+)/)
        if (match) {
          currentStage.value = match[3].trim()
        }
        // 输出消息日志（避免重复）
        if (data.message !== lastLoggedMessage) {
          lastLoggedMessage = data.message
          addLog(data.message)
        }
      }
      
      // 检查是否完成
      if (data.status === 'completed' || data.status === 'ready' || data.already_prepared) {
        addLog(t('log.prepareComplete'))
        stopPolling()
        stopProfilesPolling()
        await loadPreparedData()
      } else if (data.status === 'failed') {
        addLog(t('log.prepareFailedWithError', { error: data.error || t('common.unknownError') }))
        setPrepareError(data.error)
        stopPolling()
        stopProfilesPolling()
      }
    }
  } catch (err) {
    console.warn('轮询状态失败:', err)
  }
}

const fetchProfilesRealtime = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId, 'reddit')
    
    if (res.success && res.data) {
      const prevCount = profiles.value.length
      profiles.value = res.data.profiles || []
      if (!poblacion.value && profiles.value.some(p => p.data_source)) cargarPoblacion()
      // 只有当 API 返回有效值时才更新，避免覆盖已有的有效值
      if (res.data.total_expected) {
        expectedTotal.value = res.data.total_expected
      }
      
      // 提取实体类型
      const types = new Set()
      profiles.value.forEach(p => {
        if (p.entity_type) types.add(p.entity_type)
      })
      entityTypes.value = Array.from(types)
      
      // 输出 Profile 生成进度日志（仅当数量变化时）
      const currentCount = profiles.value.length
      if (currentCount > 0 && currentCount !== lastLoggedProfileCount) {
        lastLoggedProfileCount = currentCount
        const total = expectedTotal.value || '?'
        const latestProfile = profiles.value[currentCount - 1]
        const profileName = latestProfile?.name || latestProfile?.username || `Agent_${currentCount}`
        if (currentCount === 1) {
          addLog(t('log.startGeneratingAgentProfiles'))
        }
        addLog(t('log.agentProfile', { current: currentCount, total: total, name: profileName, profession: latestProfile?.profession || t('step2.unknownProfession') }))

        // 如果全部生成完成
        if (expectedTotal.value && currentCount >= expectedTotal.value) {
          addLog(t('log.allProfilesComplete', { count: currentCount }))
        }
      }
    }
  } catch (err) {
    console.warn('获取 Profiles 失败:', err)
  }
}

// 配置轮询
const startConfigPolling = () => {
  configTimer = setInterval(fetchConfigRealtime, 2000)
}

const stopConfigPolling = () => {
  if (configTimer) {
    clearInterval(configTimer)
    configTimer = null
  }
}

// Safety net: if the simulation state has failed but the task-level poll
// never surfaced it (e.g. prepare died before creating a task), this
// short-circuit detects it from /api/simulation/:id and stops all polling
// with a clear error message.
let _simFailedDetected = false
const checkSimulationFailed = async () => {
  if (_simFailedDetected || !props.simulationId) return false
  try {
    const res = await getSimulation(props.simulationId)
    const status = res?.data?.status
    if (status === 'failed') {
      _simFailedDetected = true
      const errText = res.data.error || t('common.unknownError')
      addLog(t('log.simulationFailed', { error: errText }))
      setPrepareError(errText)
      stopPolling()
      stopProfilesPolling()
      stopConfigPolling()
      emit('update-status', 'error')
      return true
    }
  } catch (_err) {
    // Network hiccup — retry on next poll tick.
  }
  return false
}

const fetchConfigRealtime = async () => {
  if (!props.simulationId) return

  // First, check the overall simulation state — if it flipped to "failed"
  // while we were polling the real-time config, stop immediately.
  if (await checkSimulationFailed()) return

  try {
    const res = await getSimulationConfigRealtime(props.simulationId)

    if (res.success && res.data) {
      const data = res.data
      
      // 输出配置生成阶段日志（避免重复）
      if (data.generation_stage && data.generation_stage !== lastLoggedConfigStage) {
        lastLoggedConfigStage = data.generation_stage
        if (data.generation_stage === 'generating_profiles') {
          addLog(t('log.generatingAgentProfileConfig'))
        } else if (data.generation_stage === 'generating_config') {
          addLog(t('log.generatingLLMConfig'))
        }
      }
      
      // 如果配置已生成
      if (data.config_generated && data.config) {
        simulationConfig.value = data.config
        addLog(t('log.configComplete'))

        // 显示详细配置摘要
        if (data.summary) {
          addLog(t('log.configSummaryAgents', { count: data.summary.total_agents }))
          addLog(t('log.configSummaryHours', { hours: data.summary.simulation_hours }))
          addLog(t('log.configSummaryPosts', { count: data.summary.initial_posts_count }))
          addLog(t('log.configSummaryTopics', { count: data.summary.hot_topics_count }))
          addLog(t('log.configSummaryPlatforms', { twitter: data.summary.has_twitter_config ? '✓' : '✗', reddit: data.summary.has_reddit_config ? '✓' : '✗' }))
        }
        
        // 显示时间配置详情
        if (data.config.time_config) {
          const tc = data.config.time_config
          addLog(t('log.timeConfigDetail', { minutes: tc.minutes_per_round, rounds: Math.floor((tc.total_simulation_hours * 60) / tc.minutes_per_round) }))
        }
        
        // 显示事件配置
        if (data.config.event_config?.narrative_direction) {
          const narrative = data.config.event_config.narrative_direction
          addLog(t('log.narrativeDirection', { direction: narrative.length > 50 ? narrative.substring(0, 50) + '...' : narrative }))
        }
        
        stopConfigPolling()
        phase.value = 4
        addLog(t('log.envSetupComplete'))
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('获取 Config 失败:', err)
  }
}

const loadPreparedData = async () => {
  phase.value = 2
  addLog(t('log.loadingExistingConfig'))

  // 最后获取一次 Profiles
  await fetchProfilesRealtime()
  await cargarPoblacion()
  addLog(t('log.loadedAgentProfiles', { count: profiles.value.length }))

  // 获取配置（使用实时接口）
  try {
    const res = await getSimulationConfigRealtime(props.simulationId)
    if (res.success && res.data) {
      if (res.data.config_generated && res.data.config) {
        simulationConfig.value = res.data.config
        addLog(t('log.configLoadSuccess'))

        // 显示详细配置摘要
        if (res.data.summary) {
          addLog(t('log.configSummaryAgents', { count: res.data.summary.total_agents }))
          addLog(t('log.configSummaryHours', { hours: res.data.summary.simulation_hours }))
          addLog(t('log.configSummaryPostsAlt', { count: res.data.summary.initial_posts_count }))
        }

        addLog(t('log.envSetupComplete'))
        phase.value = 4
        emit('update-status', 'completed')
      } else {
        // 配置尚未生成，开始轮询
        addLog(t('log.configGenerating'))
        startConfigPolling()
      }
    }
  } catch (err) {
    addLog(t('log.loadConfigFailed', { error: err.message }))
    setPrepareError(err?.response?.data?.error || err.message)
    emit('update-status', 'error')
  }
}

// Scroll log to bottom
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

// La ficha de una persona se cierra también con Esc
const onKeydown = (e) => { if (e.key === 'Escape' && selectedProfile.value) selectedProfile.value = null }

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  // 自动开始准备流程
  if (props.simulationId) {
    addLog(t('log.step2Init'))
    loadRunStatus()
    await iniciarEstadoCis()    // antes de preparar: hay que saber si hay banco y qué valor lleva el interruptor
    startPrepareSimulation()
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  stopPolling()
  stopProfilesPolling()
  stopConfigPolling()
})

// Razonamiento de la configuración, partido en apartados legibles (ver lib/reasoningText.js)
const reasoningBlocks = computed(() => reasoningSections(simulationConfig.value?.generation_reasoning))
</script>

<style scoped>
.ro-note {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--kb-surface-2);
  color: var(--kb-text-2);
  font-size: 13px;
  line-height: 1.45;
}
.env-setup-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--kb-surface-2);
  font-family: var(--kb-font-sans);
}

.step2-action-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 24px;
  background: var(--kb-surface);
  border-top: 1px solid var(--kb-line);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.04);
}
.action-bar-rounds { display: flex; align-items: baseline; gap: 8px; font-size: 14px; }
.action-bar-label { font: 500 11px var(--kb-font-mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--kb-muted); }
.action-bar-rounds strong { font-size: 18px; font-weight: 800; }
.action-bar-adjust {
  background: none; border: none; padding: 0 4px; cursor: pointer; min-height: 24px;
  font: 500 13px var(--kb-font-sans); color: var(--kb-accent-text); text-decoration: underline; text-underline-offset: 3px;
}

/* Error de preparación: claro, arriba, con el detalle técnico plegado */
.prepare-error {
  padding: 14px 16px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-danger-line);
  border-left-width: 4px;
  border-radius: 8px;
}
.prepare-error-title { margin: 0 0 4px; font-size: 14px; font-weight: 700; color: var(--kb-text); }
.prepare-error-text { margin: 0; font-size: 13px; line-height: 1.5; color: var(--kb-text-2); }
.prepare-error-details { margin-top: 8px; font-size: 12px; color: var(--kb-muted); }
.prepare-error-details summary { cursor: pointer; }
.prepare-error-details code {
  display: block; margin-top: 6px; padding: 8px 10px; white-space: pre-wrap;
  background: var(--kb-surface-2); border: 1px solid var(--kb-line); border-radius: 6px;
  font-family: var(--kb-font-mono); font-size: 12px; color: var(--kb-text-2); overflow-wrap: anywhere;
}
.action-bar-start { width: auto; padding-left: 20px; padding-right: 20px; }

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Step Card */
.step-card {
  background: #FFF;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid var(--kb-line);
  transition: all 0.3s ease;
  position: relative;
}

.step-card.active {
  border-color: var(--kb-accent-line);
  box-shadow: 0 4px 12px rgba(204, 230, 115, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Número de los pasos pendientes: --kb-control-line (3,69:1, texto grande en negrita ≥ 3:1); el #DDD daba 1,36:1 */
.step-num {
  font-family: var(--kb-font-mono);
  font-size: 20px;
  font-weight: 700;
  color: var(--kb-control-line);
}

.step-card.active .step-num,
.step-card.completed .step-num {
  color: var(--kb-text);
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}

/* Estados: rótulo mono corto en mayúsculas (11 px) y colores de la marca; el texto ya dice el estado */
.badge {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.badge.success { background: var(--kb-ok-bg); color: var(--kb-ok-text); }
.badge.processing { background: var(--kb-accent-solid); color: var(--kb-accent-on); }
.badge.pending { background: var(--kb-soft); color: var(--kb-text-on-soft); }
.badge.error { background: var(--kb-surface); color: var(--kb-danger-text); border: 1px solid var(--kb-danger-line); padding: 3px 7px; }

.card-content {
  /* No extra padding - uses step-card's padding */
}

.api-note {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  color: var(--kb-subtle);
  margin-bottom: 8px;
}

.description {
  font-size: 12px;
  color: var(--kb-muted);
  line-height: 1.5;
  margin-bottom: 16px;
}

/* Action Section */
.action-section {
  margin-top: 16px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn.primary {
  background: var(--kb-text);
  color: #FFF;
}

.action-btn.primary:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn.secondary {
  background: var(--kb-soft);
  color: var(--kb-text-2);
}

.action-btn.secondary:hover:not(:disabled) {
  background: var(--kb-line);
}

/* La misma acción que la barra fija, en contorno: un solo botón relleno a la vista */
.action-btn.outline {
  background: var(--kb-surface);
  color: var(--kb-text);
  border: 1px solid var(--kb-control-line);
  padding: 11px 23px;
}

.action-btn.outline:hover:not(:disabled) {
  border-color: var(--kb-text);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-group {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.action-group.dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.action-group.dual .action-btn {
  width: 100%;
}

/* Info Card */
.info-card {
  background: var(--kb-soft);
  border-radius: 6px;
  padding: 16px;
  margin-top: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed var(--kb-line);
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 12px;
  color: var(--kb-muted);
}

.info-value {
  font-size: 13px;
  font-weight: 500;
}

.info-value.mono {
  font-family: var(--kb-font-mono);
  font-size: 12px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  background: var(--kb-surface-2);
  padding: 16px;
  border-radius: 6px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--kb-text);
  font-family: var(--kb-font-sans);
}

.stat-label {
  font-size: 12px;
  color: var(--kb-subtle);
  margin-top: 4px;
  display: block;
}

/* Profiles Preview */
.profiles-preview {
  margin-top: 20px;
  border-top: 1px solid var(--kb-line);
  padding-top: 16px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.preview-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.preview-count {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  color: var(--kb-subtle);
  font-weight: 600;
}

/* ─── Agent Explorer controls ─────────────────────────────────── */
.demographics-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.demo-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* Chips de filtro: botones de verdad (teclado), borde de control (≥ 3:1) y 24 px de alto como mínimo */
.demo-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 24px;
  padding: 3px 10px;
  border: 1px solid var(--kb-control-line);
  border-radius: 999px;
  background: #FFF;
  color: var(--kb-text-2);
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.demo-chip:hover {
  border-color: var(--kb-text);
  color: var(--kb-text);
}

.demo-chip.active {
  background: var(--kb-text);
  color: #FFF;
  border-color: var(--kb-text);
}

.demo-chip.subtle {
  background: var(--kb-soft);
  border-color: var(--kb-control-line);
  color: var(--kb-text-on-soft);
}

.demo-chip.subtle.active {
  background: var(--kb-text);
  color: #FFF;
  border-color: var(--kb-text);
}

/* Público con datos reales (CIS) */
.cis-toggle { margin: 14px 0; padding: 12px 14px; border: 1px solid var(--kb-control-line); border-radius: 10px; background: var(--kb-soft); }
.cis-toggle-row { display: flex; gap: 12px; align-items: flex-start; cursor: pointer; }
.cis-check { width: 20px; height: 20px; margin-top: 2px; accent-color: var(--kb-text); flex: none; }
.cis-toggle-text { display: flex; flex-direction: column; gap: 2px; }
.cis-toggle-title { font-weight: 700; font-size: 14px; color: var(--kb-text); }
.cis-toggle-desc { font-size: 12.5px; color: var(--kb-text-2); line-height: 1.45; }
.cis-changed { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 10px; font-size: 12.5px; color: var(--kb-text); }
.cis-regen { min-height: 32px; padding: 4px 14px; border: 1px solid var(--kb-text); border-radius: 999px; background: var(--kb-text); color: #FFF; font: inherit; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.cis-reparto { margin: 14px 0; padding: 14px; border: 1px solid var(--kb-control-line); border-radius: 10px; background: #FFF; }
.cis-reparto-head { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; align-items: baseline; }
.cis-reparto-title { font-weight: 700; font-size: 14px; color: var(--kb-text); }
.cis-source { font-size: 12px; font-weight: 600; color: var(--kb-text-on-soft); background: var(--kb-soft); border-radius: 999px; padding: 2px 10px; }
.cis-reparto-sub { margin: 4px 0 10px; font-size: 12.5px; color: var(--kb-text-2); }
.cis-bars { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px 24px; }
.cis-group { display: flex; flex-direction: column; gap: 5px; }
.cis-group-title { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--kb-text-2); font-weight: 700; }
.cis-bar-row { display: grid; grid-template-columns: 96px 1fr 38px; gap: 8px; align-items: center; font-size: 12px; color: var(--kb-text); }
.cis-bar-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cis-bar-track { height: 8px; border-radius: 4px; background: var(--kb-soft); overflow: hidden; }
.cis-bar-fill { display: block; height: 100%; background: var(--kb-text); border-radius: 4px; }
.cis-bar-pct { text-align: right; font-variant-numeric: tabular-nums; color: var(--kb-text-2); }
.cis-filters, .cis-relaxed { margin: 10px 0 0; font-size: 12px; color: var(--kb-text-2); }
.cis-relaxed { font-weight: 600; color: var(--kb-text); }
.cis-tag { display: inline-block; font-size: 11.5px; font-weight: 600; color: var(--kb-text-on-soft); background: var(--kb-soft); border: 1px solid var(--kb-control-line); border-radius: 999px; padding: 1px 8px; margin-left: 6px; }
.cis-modal { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.cis-modal .cis-tag { margin-left: 0; }
.cis-facts { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.5; color: var(--kb-text-2); }

.profiles-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}

.search-wrapper {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  font-size: 14px;
  color: var(--kb-subtle);
  pointer-events: none;
}

.profiles-search {
  width: 100%;
  min-height: 32px;
  padding: 7px 34px 7px 30px;
  border: 1px solid var(--kb-control-line);
  border-radius: 6px;
  background: #FFF;
  font-family: inherit;
  font-size: 12px;
  color: var(--kb-text);
  outline: none;
  box-sizing: border-box;
}

.profiles-search:focus {
  border-color: var(--kb-text);
}

.profiles-search:focus-visible {
  outline: 2px solid var(--kb-text);
  outline-offset: 1px;
}

.profiles-search::placeholder {
  color: var(--kb-subtle);
}

.clear-btn {
  position: absolute;
  right: 4px;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  background: var(--kb-line);
  color: var(--kb-text-2);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.clear-btn:hover {
  background: var(--kb-text);
  color: #FFF;
}

.profiles-sort {
  min-height: 32px;
  padding: 7px 10px;
  border: 1px solid var(--kb-control-line);
  border-radius: 6px;
  background: #FFF;
  font-family: inherit;
  font-size: 12px;
  color: var(--kb-text-2);
  cursor: pointer;
  outline: none;
}

.profiles-sort:hover,
.profiles-sort:focus {
  border-color: var(--kb-text);
}

.profiles-sort:focus-visible {
  outline: 2px solid var(--kb-text);
  outline-offset: 1px;
}

.profiles-empty {
  padding: 24px;
  text-align: center;
  color: var(--kb-subtle);
  font-size: 13px;
  font-style: italic;
  background: var(--kb-surface-2);
  border: 1px dashed var(--kb-line-strong);
  border-radius: 6px;
}

.profiles-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-height: 320px;
  overflow-y: auto;
  padding-right: 4px;
}

.profiles-list::-webkit-scrollbar {
  width: 4px;
}

.profiles-list::-webkit-scrollbar-thumb {
  background: var(--kb-line-strong);
  border-radius: 2px;
}

.profiles-list::-webkit-scrollbar-thumb:hover {
  background: var(--kb-line-strong);
}

.profile-card {
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profile-card:hover {
  border-color: var(--kb-subtle);
  background: #FFF;
}

.profile-card:focus-visible {
  outline: 2px solid var(--kb-text);
  outline-offset: 2px;
  background: #FFF;
}

.profile-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}

.profile-realname {
  font-size: 14px;
  font-weight: 700;
  color: var(--kb-text);
}

.profile-username {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  color: var(--kb-subtle);
  overflow-wrap: anywhere;
}

.profile-meta {
  margin-bottom: 8px;
}

.profile-profession {
  font-size: 12px;
  color: var(--kb-text-on-soft);
  background: var(--kb-soft);
  padding: 2px 8px;
  border-radius: 3px;
}

.profile-bio {
  font-size: 12px;
  color: var(--kb-text-2);
  line-height: 1.6;
  margin: 0 0 10px 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.profile-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* Temas: lima muy claro con texto oliva (5,3:1), no el azul de antes, ajeno a la marca */
.topic-tag {
  font-size: 12px;
  color: var(--kb-accent-text);
  background: var(--kb-accent-subtle);
  padding: 2px 8px;
  border-radius: 10px;
}

.topic-more {
  font-size: 12px;
  color: var(--kb-subtle);
  padding: 2px 6px;
}

/* Config Preview */
/* Config Detail Panel */
.config-detail-panel {
  margin-top: 16px;
}

.config-block {
  margin-top: 16px;
  border-top: 1px solid var(--kb-line);
  padding-top: 12px;
}

.config-block:first-child {
  margin-top: 0;
  border-top: none;
  padding-top: 0;
}

.config-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.config-block-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-block-badge {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  background: var(--kb-soft);
  color: var(--kb-text-on-soft);
  padding: 2px 8px;
  border-radius: 10px;
}

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.config-item {
  background: var(--kb-surface-2);
  padding: 12px 14px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-item-label {
  font-size: 12px;
  color: var(--kb-subtle);
}

.config-item-value {
  font-family: var(--kb-font-sans);
  font-size: 16px;
  font-weight: 600;
  color: var(--kb-text);
}

/* Time Periods */
.time-periods {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.period-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--kb-surface-2);
  border-radius: 6px;
}

.period-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--kb-muted);
  min-width: 70px;
}

.period-hours {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  color: var(--kb-text-2);
  flex: 1;
}

.period-multiplier {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--kb-accent-text);
  background: var(--kb-accent-subtle);
  padding: 2px 6px;
  border-radius: 4px;
}

/* Agents Cards */
.agents-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.agents-more {
  margin-top: 12px;
  width: 100%;
  padding: 10px;
  background: var(--kb-surface-2);
  border: 1px dashed var(--kb-line-strong);
  border-radius: 6px;
  font: 500 13px var(--kb-font-sans);
  color: var(--kb-text);
  cursor: pointer;
}
.agents-more:hover { border-color: var(--kb-accent-text); color: var(--kb-accent-text); }

.agents-cards::-webkit-scrollbar {
  width: 4px;
}

.agents-cards::-webkit-scrollbar-thumb {
  background: var(--kb-line-strong);
  border-radius: 2px;
}

.agents-cards::-webkit-scrollbar-thumb:hover {
  background: var(--kb-line-strong);
}

.agent-card {
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
  padding: 14px;
  transition: all 0.2s ease;
}

.agent-card:hover {
  border-color: var(--kb-subtle);
  background: #FFF;
}

/* Agent Card Header */
.agent-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--kb-soft);
}

.agent-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-id {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  color: var(--kb-subtle);
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--kb-text);
}

.agent-tags {
  display: flex;
  gap: 6px;
}

.agent-tags {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.agent-type {
  font-size: 12px;
  color: var(--kb-text-on-soft);
  background: var(--kb-soft);
  padding: 2px 8px;
  border-radius: 4px;
}

/* Postura: el texto (traducido) dice cuál es; el color de marca solo acompaña */
.agent-stance {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 1px 7px;
  border-radius: 4px;
  border: 1px solid transparent;
  white-space: nowrap;
}

.stance-neutral {
  background: var(--kb-soft);
  color: var(--kb-text-on-soft);
}

.stance-supportive {
  background: var(--kb-ok-bg);
  color: var(--kb-ok-text);
  border-color: var(--kb-ok-line);
}

.stance-opposing {
  background: var(--kb-surface);
  color: var(--kb-danger-text);
  border-color: var(--kb-danger-line);
}

.stance-observer {
  background: var(--kb-surface);
  color: var(--kb-text-2);
  border: 1px dashed var(--kb-control-line);
}

/* Agent Timeline */
.agent-timeline {
  margin-bottom: 14px;
}

.timeline-label {
  display: block;
  font-size: 12px;
  color: var(--kb-subtle);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mini-timeline {
  display: flex;
  gap: 2px;
  height: 16px;
  background: var(--kb-surface-2);
  border-radius: 4px;
  padding: 3px;
}

.timeline-hour {
  flex: 1;
  background: var(--kb-line);
  border-radius: 2px;
  transition: all 0.2s;
}

.timeline-hour.active {
  background: var(--kb-accent-solid);
}

.timeline-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-family: var(--kb-font-mono);
  font-size: 11px;
  color: var(--kb-subtle);
}

/* Agent Params */
.agent-params {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.param-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-item .param-label {
  font-size: 12px;
  color: var(--kb-subtle);
}

.param-item .param-value {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-text-2);
}

.param-value.with-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-bar {
  height: 4px;
  background: var(--kb-accent-hover);
  border-radius: 2px;
  min-width: 4px;
  max-width: 40px;
}

/* el signo (+/−) ya dice el sentido; el color de marca lo acompaña */
.param-value.positive {
  color: var(--kb-ok-text);
}

.param-value.negative {
  color: var(--kb-danger-text);
}

.param-value.neutral {
  color: var(--kb-muted);
}

.param-value.highlight {
  color: var(--kb-accent-text);
}

/* Platforms Grid */
.platforms-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.platform-card {
  background: var(--kb-surface-2);
  padding: 14px;
  border-radius: 6px;
}

.platform-card-header {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--kb-line);
}

.platform-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text-2);
}

.platform-params {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.param-label {
  font-size: 12px;
  color: var(--kb-muted);
}

.param-value {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-text);
}

/* Reasoning Content */
.reasoning-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reasoning-item {
  padding: 16px 20px 18px;
  background: var(--kb-surface-2);
  border-radius: 8px;
}

/* Título del apartado: como las etiquetas del resto de la pantalla (mono, versalitas, discreto) */
.reasoning-label {
  margin: 0 0 10px;
  font: 600 11px/1.3 var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kb-muted);
}

/* Texto: ~66 caracteres por línea (60–75 se lee bien; antes pasaba de 110), interlineado 1,6 y sin viudas */
.reasoning-text {
  max-width: 66ch;
  font-size: 14px;
  color: var(--kb-text-2);
  line-height: 1.6;
  margin: 0 0 0.75em;
  text-wrap: pretty;
}
.reasoning-list {
  max-width: 66ch;
  margin: 0 0 0.75em;
  padding-left: 1.25em;
  font-size: 14px;
  color: var(--kb-text-2);
  line-height: 1.6;
  text-wrap: pretty;
}
.reasoning-list li { margin: 0 0 0.45em; padding-left: 0.2em; }
.reasoning-list li::marker { color: var(--kb-accent-text); font-weight: 600; }
.reasoning-item > :last-child { margin-bottom: 0; }

/* Profile Modal */
.profile-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.profile-modal {
  background: #FFF;
  border-radius: 16px;
  width: 90%;
  max-width: 600px;
  max-height: 85vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 24px;
  background: #FFF;
  border-bottom: 1px solid var(--kb-soft);
}

.modal-header-info {
  flex: 1;
}

.modal-name-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}

.modal-realname {
  font-size: 20px;
  font-weight: 700;
  color: var(--kb-text);
}

.modal-username {
  font-family: var(--kb-font-mono);
  font-size: 13px;
  color: var(--kb-subtle);
}

.modal-profession {
  font-size: 12px;
  color: var(--kb-muted);
  background: var(--kb-soft);
  padding: 4px 10px;
  border-radius: 4px;
  display: inline-block;
  font-weight: 500;
}

.close-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: none;
  color: var(--kb-text-2);
  border-radius: 50%;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: color 0.2s;
  padding: 0;
}

.close-btn:hover {
  color: var(--kb-text-2);
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

/* 基本信息网格 */
.modal-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px 16px;
  margin-bottom: 32px;
  padding: 0;
  background: transparent;
  border-radius: 0;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: var(--kb-subtle);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--kb-text-2);
}

.info-value.mbti {
  font-family: var(--kb-font-mono);
  color: var(--kb-accent-text);
}

/* 模块区域 */
.modal-section {
  margin-bottom: 28px;
}

.section-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-subtle);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.section-bio {
  font-size: 14px;
  color: var(--kb-text-2);
  line-height: 1.6;
  margin: 0;
  padding: 16px;
  background: var(--kb-surface-2);
  border-radius: 6px;
  border-left: 3px solid var(--kb-line);
}

/* 话题标签 */
.topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-item {
  font-size: 12px;
  color: var(--kb-accent-text);
  background: var(--kb-accent-subtle);
  padding: 4px 10px;
  border-radius: 12px;
  border: none;
}

/* 详细人设 */
.persona-dimensions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.dimension-card {
  background: var(--kb-surface-2);
  padding: 12px;
  border-radius: 6px;
  border-left: 3px solid var(--kb-line-strong);
  transition: all 0.2s;
}

.dimension-card:hover {
  background: var(--kb-soft);
  border-left-color: var(--kb-subtle);
}

.dim-title {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--kb-text-2);
  margin-bottom: 4px;
}

.dim-desc {
  display: block;
  font-size: 12px;
  color: var(--kb-subtle);
  line-height: 1.4;
}

.persona-content {
  max-height: none;
  overflow: visible;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
}

.persona-content::-webkit-scrollbar {
  width: 4px;
}

.persona-content::-webkit-scrollbar-thumb {
  background: var(--kb-line-strong);
  border-radius: 2px;
}

.section-persona {
  font-size: 13px;
  color: var(--kb-text-2);
  line-height: 1.8;
  margin: 0;
  text-align: justify;
}

/* System Logs */
.system-logs {
  background: var(--kb-text);
  color: var(--kb-line-strong);
  padding: 16px;
  font-family: var(--kb-font-mono);
  border-top: 1px solid var(--kb-text);
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--kb-text-2);
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--kb-muted-on-dark);
}

/* Sobre tinta, el gris de texto da 3,7:1: el rótulo va en --kb-muted-on-dark (5,5:1) */
.log-title { color: var(--kb-muted-on-dark); font-size: 12px; flex-shrink: 0; }
/* el botón global medía 22 px de alto: el mínimo táctil es 24 (WCAG 2.5.8) */
.log-toggle { min-height: 24px; }

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 80px; /* Approx 4 lines visible */
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: var(--kb-text-2);
  border-radius: 2px;
}

.log-line {
  font-size: 12px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: var(--kb-muted-on-dark);
  min-width: 75px;
}

.log-msg {
  color: var(--kb-line-strong);
  word-break: break-all;
}

/* Spinner */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid var(--kb-line);
  border-top-color: var(--kb-accent-line);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
/* Orchestration Content */
.orchestration-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 16px;
}

.box-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.narrative-box {
  background: #FFFFFF;
  padding: 20px 24px;
  border-radius: 12px;
  border: 1px solid var(--kb-line);
  box-shadow: 0 4px 24px rgba(0,0,0,0.03);
  transition: all 0.3s ease;
}

.narrative-box .special-icon { color: var(--kb-text); }

.narrative-box .box-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--kb-muted);
  font-size: 13px;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  font-weight: 600;
}

.special-icon {
  filter: drop-shadow(0 2px 4px rgba(204, 230, 115, 0.2));
  transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.narrative-box:hover .special-icon {
  transform: rotate(180deg);
}

.narrative-text {
  font-family: var(--kb-font-sans);
  font-size: 14px;
  color: var(--kb-text-2);
  line-height: 1.8;
  margin: 0;
  letter-spacing: 0.01em;
}

/* Markdown (MiniMarkdown) dentro de los textos que escribe el modelo */
.narrative-text :deep(.md-p),
.post-text :deep(.md-p),
.section-bio :deep(.md-p),
.section-persona :deep(.md-p) { margin: 0 0 8px; }
.narrative-text :deep(.md-p:last-child),
.post-text :deep(.md-p:last-child),
.section-bio :deep(.md-p:last-child),
.section-persona :deep(.md-p:last-child) { margin-bottom: 0; }
.narrative-text :deep(.md-ul), .narrative-text :deep(.md-ol),
.post-text :deep(.md-ul), .post-text :deep(.md-ol),
.section-persona :deep(.md-ul), .section-persona :deep(.md-ol) { margin: 0 0 8px; padding-left: 20px; }
.narrative-text :deep(strong), .post-text :deep(strong),
.section-bio :deep(strong), .section-persona :deep(strong), .profile-bio :deep(strong) { font-weight: 700; color: var(--kb-text); }
.post-text :deep(.md-quote), .section-persona :deep(.md-quote) { margin: 0 0 8px; padding-left: 10px; border-left: 2px solid var(--kb-line-strong); }

.topics-section {
  background: #FFF;
}

.hot-topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hot-topic-tag {
  font-size: 12px;
  color: var(--kb-accent-text);
  background: var(--kb-accent-subtle);
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.hot-topic-more {
  font-size: 11px;
  color: var(--kb-subtle);
  padding: 4px 6px;
}

.initial-posts-section {
  border-top: 1px solid var(--kb-line);
  padding-top: 16px;
}

.posts-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-left: 8px;
  border-left: 2px solid var(--kb-soft);
  margin-top: 12px;
}

.timeline-item {
  position: relative;
  padding-left: 20px;
}

.timeline-marker {
  position: absolute;
  left: 0;
  top: 14px;
  width: 12px;
  height: 2px;
  background: var(--kb-line-strong);
}

.timeline-content {
  background: var(--kb-surface-2);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--kb-line);
}

.post-header {
  display: flex;
  justify-content: space-between;
  gap: 4px 12px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.post-role {
  font-size: 12px;
  font-weight: 700;
  color: var(--kb-text-2);
  text-transform: uppercase;
}

.post-agent-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.post-id,
.post-username {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  color: var(--kb-muted);
  line-height: 1.3;
  vertical-align: baseline;
}

.post-username {
  margin-right: 6px;
  overflow-wrap: anywhere;
}

.post-text {
  font-size: 13px;
  color: var(--kb-text-2);
  line-height: 1.5;
  margin: 0;
}

/* 模拟轮数配置样式 */
.rounds-config-section {
  margin: 24px 0;
  padding-top: 24px;
  border-top: 1px solid var(--kb-line);
}

.rounds-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--kb-text);
}

.section-desc {
  font-size: 12px;
  color: var(--kb-subtle);
}

.desc-highlight {
  font-family: var(--kb-font-mono);
  font-weight: 600;
  color: var(--kb-text);
  background: var(--kb-soft);
  padding: 1px 6px;
  border-radius: 4px;
  margin: 0 2px;
}

/* Switch Control */
.switch-control {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px 4px 4px;
  border-radius: 20px;
  transition: background 0.2s;
}

.switch-control:hover {
  background: var(--kb-surface-2);
}

/* El interruptor sigue siendo un checkbox de verdad (se enfoca con Tab), solo que invisible: con display:none no había teclado */
.switch-control {
  position: relative;
}

.switch-control .switch-input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  margin: 0;
}

.switch-control .switch-input:focus-visible + .switch-track {
  outline: 2px solid var(--kb-text);
  outline-offset: 2px;
}

.switch-track {
  width: 36px;
  height: 20px;
  background: var(--kb-line);
  border-radius: 10px;
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
}

.switch-track::after {
  content: '';
  position: absolute;
  left: 2px;
  top: 2px;
  width: 16px;
  height: 16px;
  background: #FFF;
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
}

.switch-control input:checked + .switch-track {
  background: var(--kb-text);
}

.switch-control input:checked + .switch-track::after {
  transform: translateX(16px);
}

.switch-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--kb-muted);
}

.switch-control input:checked ~ .switch-label {
  color: var(--kb-text);
}

/* Slider Content */
.rounds-content {
  animation: fadeIn 0.3s ease;
}

.slider-display {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}

.slider-main-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.val-num {
  font-family: var(--kb-font-sans);
  font-size: 24px;
  font-weight: 700;
  color: var(--kb-text);
}

.val-unit {
  font-size: 12px;
  color: var(--kb-muted);
  font-weight: 500;
}

.slider-meta-info {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  color: var(--kb-text-on-soft);
  background: var(--kb-soft);
  padding: 4px 8px;
  border-radius: 4px;
}

.range-wrapper {
  position: relative;
  padding: 0 2px;
}

.minimal-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  background: var(--kb-line);
  border-radius: 2px;
  outline: none;
  background-image: linear-gradient(var(--kb-text), var(--kb-text));
  background-size: var(--percent, 0%) 100%;
  background-repeat: no-repeat;
  cursor: pointer;
}

.minimal-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #FFF;
  border: 2px solid var(--kb-text);
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  transition: transform 0.1s;
  margin-top: -6px; /* Center thumb */
}

.minimal-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.minimal-slider::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
}

.range-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-family: var(--kb-font-mono);
  font-size: 11px;
  color: var(--kb-subtle);
  position: relative;
}

.mark-recommend {
  cursor: pointer;
  transition: color 0.2s;
  position: relative;
  min-height: 24px;
  padding: 0 4px;
  margin-top: -4px;
  background: none;
  border: 0;
  font: inherit;
  color: var(--kb-subtle);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.mark-recommend:hover {
  color: var(--kb-text);
}

.mark-recommend.active {
  color: var(--kb-text);
  font-weight: 600;
}

.mark-recommend::after {
  content: '';
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  width: 1px;
  height: 4px;
  background: var(--kb-line-strong);
}

/* Auto Info */
.auto-info-card {
  display: flex;
  align-items: center;
  gap: 24px;
  background: var(--kb-surface-2);
  padding: 16px 20px;
  border-radius: 8px;
}

.auto-value {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 4px;
  padding-right: 24px;
  border-right: 1px solid var(--kb-line);
}

.auto-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
}

.auto-meta-row {
  display: flex;
  align-items: center;
}

.duration-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--kb-font-mono);
  font-size: 12px;
  font-weight: 500;
  color: var(--kb-muted);
  background: #FFFFFF;
  border: 1px solid var(--kb-line);
  padding: 3px 8px;
  border-radius: 6px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}

.auto-desc {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auto-desc p {
  margin: 0;
  font-size: 13px;
  color: var(--kb-muted);
  line-height: 1.5;
}

.highlight-tip {
  margin-top: 4px;
  padding: 0;
  background: none;
  border: 0;
  text-align: left;
  font: 500 12px/1.5 var(--kb-font-sans);
  color: var(--kb-text);
  cursor: pointer;
}

.highlight-tip:hover {
  text-decoration: underline;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Modal Transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .profile-modal {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.modal-leave-active .profile-modal {
  transition: all 0.3s ease-in;
}

.modal-enter-from .profile-modal,
.modal-leave-to .profile-modal {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}

/* Nombres de agente: los modelos los generan con guiones bajos y sin espacios («marca_que_busca_proyectar_modernidad_…»),
   y una palabra sin huecos no parte nunca: salía por el borde del panel. Parten donde haga falta. */
.profile-realname,
.modal-realname,
.modal-username {
  overflow-wrap: anywhere;
  min-width: 0;
}
</style>
