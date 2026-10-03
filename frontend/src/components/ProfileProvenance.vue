<template>
  <div class="profile-provenance" :class="{ compact }">
    <span class="origin-tag">{{ $t(`profiles.origin.${origin}`) }}</span>
    <template v-if="!compact">
      <p class="origin-note">{{ $t(`profiles.description.${origin}`) }}</p>
      <p v-if="styleKeys.length" class="origin-note">{{ $t('profiles.simulatedStyle') }}: {{ styleKeys.map(key => $t(key)).join(' · ') }}</p>
      <details v-if="passages.length" class="origin-material">
        <summary>{{ $t('profiles.sourcePassages') }}</summary>
        <blockquote v-for="(passage, index) in passages" :key="index">{{ passage.text }}</blockquote>
      </details>
      <p v-if="passages.length && profile.source_coverage?.omitted > 0" class="origin-note">{{ $t('profiles.partialMaterial') }}</p>
      <details v-if="origin === 'synthetic' && typeof profile.fictional_biography === 'string' && profile.fictional_biography.trim()" class="origin-material">
        <summary>{{ $t('profiles.fictionalBiography') }}</summary>
        <p class="fictional-biography">{{ profile.fictional_biography }}</p>
      </details>
      <details v-if="origin === 'survey' && profile.survey_facts?.length" class="origin-material">
        <summary>{{ $t('profiles.surveyFacts') }}</summary>
        <ul><li v-for="(fact, index) in profile.survey_facts" :key="index">{{ fact }}</li></ul>
      </details>
    </template>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { profileOrigin, profilePassages, profileStyleKeys } from '../lib/profilePresentation'
const props = defineProps({ profile: { type: Object, required: true }, compact: Boolean })
const origin = computed(() => profileOrigin(props.profile))
const passages = computed(() => profilePassages(props.profile))
const styleKeys = computed(() => profileStyleKeys(props.profile))
</script>
<style scoped>
.profile-provenance { margin: 6px 0 12px; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.profile-provenance.compact { margin: 4px 0; }
.origin-tag { display: inline-block; padding: 2px 6px; border: 1px solid var(--kb-line-strong); border-radius: 3px; font-size: 12px; font-weight: 600; }
.origin-note { margin: 5px 0; color: var(--kb-muted); }
.origin-material { margin-top: 8px; }
.origin-material summary { min-height: 24px; padding-block: 3px; cursor: pointer; font-weight: 600; }
.origin-material summary:focus-visible { outline: 2px solid var(--kb-text); outline-offset: 2px; }
.fictional-biography { white-space: pre-wrap; margin: 8px 0; }
.origin-material blockquote { margin: 8px 0; padding-left: 10px; border-left: 2px solid var(--kb-line-strong); white-space: pre-wrap; }
.origin-material ul { margin: 8px 0; padding-left: 20px; }
</style>
