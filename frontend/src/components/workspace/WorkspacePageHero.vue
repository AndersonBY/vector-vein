<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: '',
  },
  stats: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <section class="workspace-page-hero">
    <div class="hero-content">
      <div class="hero-copy">
        <a-typography-title :level="2" class="hero-title">
          {{ title }}
        </a-typography-title>
        <a-typography-paragraph v-if="description" type="secondary" class="hero-description">
          {{ description }}
        </a-typography-paragraph>
        <a-flex wrap gap="small" class="hero-actions">
          <slot name="actions" />
        </a-flex>
      </div>
      <div v-if="stats.length" class="hero-stats">
        <div v-for="stat in stats" :key="stat.label" class="hero-stat-card">
          <a-typography-text type="secondary" class="hero-stat-label">
            {{ stat.label }}
          </a-typography-text>
          <div class="hero-stat-value">
            {{ stat.value }}
          </div>
          <a-typography-text v-if="stat.tip" type="secondary" class="hero-stat-tip">
            {{ stat.tip }}
          </a-typography-text>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.workspace-page-hero {
  border: 1px solid var(--hero-surface-border);
  border-radius: 24px;
  padding: 24px;
  color: var(--site-text-color);
  background:
    radial-gradient(circle at top left, var(--hero-surface-glow), transparent 34%),
    linear-gradient(135deg, var(--hero-surface-background-start), var(--hero-surface-background-end));
  box-shadow: var(--hero-surface-shadow);
}

.hero-content {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.9fr);
  gap: 20px;
  align-items: start;
}

.hero-title {
  margin-bottom: 8px;
}

.hero-description {
  margin-bottom: 0;
  max-width: 720px;
}

.hero-actions {
  margin-top: 20px;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.hero-stat-card {
  min-height: 112px;
  padding: 16px;
  border-radius: 18px;
  background: var(--hero-stat-background);
  border: 1px solid var(--hero-stat-border);
  backdrop-filter: blur(8px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.hero-stat-label,
.hero-stat-tip {
  font-size: 12px;
}

.hero-stat-value {
  margin-top: 8px;
  font-size: 28px;
  line-height: 1;
  font-weight: 700;
  color: var(--hero-stat-value-color);
}

.hero-stat-tip {
  display: block;
  margin-top: 8px;
}

@media (max-width: 960px) {
  .workspace-page-hero {
    padding: 18px;
  }

  .hero-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hero-stats {
    grid-template-columns: 1fr 1fr;
  }

  .hero-stat-value {
    font-size: 24px;
  }
}
</style>
