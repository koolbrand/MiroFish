<template>
  <div class="result-references">
    <p v-for="ref in sourceRefs" :key="ref.section_index" class="result-source">{{ $t('reportResults.section', { n: ref.section_index }) }} · {{ ref.section_title }}</p>
    <details>
    <summary>{{ $t('reportResults.references') }}</summary>
    <p class="reference-context">{{ $t('reportResults.referenceContext') }}</p>
    <figure v-for="(ref, index) in refs" :key="index">
      <figcaption>{{ $t('reportResults.section', { n: ref.section_index }) }} · {{ ref.section_title }}</figcaption>
      <blockquote>{{ ref.quote }}</blockquote>
    </figure>
    </details>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ refs: { type: Array, default: () => [] } })
const sourceRefs = computed(() => props.refs.filter((ref, index, list) => list.findIndex(other => other.section_index === ref.section_index) === index))
</script>
<style scoped>
.result-references { font-size: 12px; line-height: 1.6; margin-top: 14px; overflow-wrap: anywhere; }
.result-source { margin: 0 0 4px; color: var(--kb-muted); font: 400 12px/1.5 var(--kb-font-mono); }
summary { cursor: pointer; min-height: 24px; padding: 4px 0; color: var(--kb-accent-text); font-weight: 500; }
summary:focus-visible { outline: 2px solid var(--kb-accent-text); outline-offset: 3px; }
.reference-context { color: var(--kb-muted); margin: 8px 0; }
figure { margin: 12px 0 0; }
figcaption { color: var(--kb-muted); font: 400 12px/1.5 var(--kb-font-mono); }
blockquote { margin: 8px 0 0; padding: 8px 12px; border-left: 2px solid var(--kb-accent-line); background: var(--kb-surface-2); color: var(--kb-text-2); white-space: pre-wrap; }
</style>
