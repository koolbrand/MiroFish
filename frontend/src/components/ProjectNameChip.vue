<template>
  <div class="project-chip" :class="{ editing: isEditing, saving }">
    <span
      v-if="!isEditing"
      class="chip-text"
      :title="$t('main.renameProject')"
      @click="startEdit"
    >
      <span class="chip-label">{{ displayName }}</span>
      <span class="chip-edit-icon" aria-hidden="true">✎</span>
    </span>
    <template v-else>
      <input
        ref="inputRef"
        v-model="draft"
        class="chip-input"
        type="text"
        maxlength="120"
        :disabled="saving"
        :placeholder="$t('home.projectNamePlaceholder')"
        @keyup.enter="commit"
        @keyup.esc="cancel"
        @blur="commit"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { renameProject } from '../api/graph'

const props = defineProps({
  projectId: { type: String, required: true },
  name: { type: String, default: '' }
})

const emit = defineEmits(['updated'])

const isEditing = ref(false)
const saving = ref(false)
const draft = ref(props.name || '')
const inputRef = ref(null)

const displayName = computed(() => {
  const n = (props.name || '').trim()
  return n || 'Unnamed Project'
})

watch(() => props.name, (v) => {
  if (!isEditing.value) draft.value = v || ''
})

const startEdit = async () => {
  if (saving.value) return
  draft.value = props.name || ''
  isEditing.value = true
  await nextTick()
  inputRef.value?.focus()
  inputRef.value?.select()
}

const cancel = () => {
  draft.value = props.name || ''
  isEditing.value = false
}

const commit = async () => {
  if (!isEditing.value) return
  const trimmed = (draft.value || '').trim()
  if (!trimmed || trimmed === (props.name || '').trim()) {
    isEditing.value = false
    return
  }
  try {
    saving.value = true
    const res = await renameProject(props.projectId, trimmed)
    if (res?.success) {
      emit('updated', res.data)
    } else {
      console.warn('No se pudo renombrar el proyecto:', res?.error)
    }
  } catch (err) {
    console.warn('Excepción al renombrar el proyecto:', err)
  } finally {
    saving.value = false
    isEditing.value = false
  }
}
</script>

<style scoped>
.project-chip {
  display: inline-flex;
  align-items: center;
  max-width: 260px;
  margin-left: 14px;
  padding: 0;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.chip-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid #E5E5E5;
  border-radius: 4px;
  background: #FAFAFA;
  color: #333;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.2px;
  cursor: pointer;
  transition: all 0.15s ease;
  max-width: 100%;
}

.chip-text:hover {
  border-color: #FF4500;
  color: #000;
  background: #FFF;
}

.chip-label {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-edit-icon {
  font-size: 11px;
  color: #999;
  transition: color 0.15s ease;
}

.chip-text:hover .chip-edit-icon {
  color: #FF4500;
}

.chip-input {
  min-width: 180px;
  max-width: 260px;
  padding: 4px 10px;
  border: 1px solid #FF4500;
  border-radius: 4px;
  background: #FFF;
  color: #000;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  outline: none;
  box-shadow: 0 0 0 2px rgba(255, 69, 0, 0.15);
}

.chip-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.project-chip.saving .chip-text {
  opacity: 0.6;
  cursor: progress;
}
</style>
