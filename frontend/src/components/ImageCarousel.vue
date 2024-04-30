<script setup>
const props = defineProps({
  images: {
    type: Array,
    required: true,
    default: () => [],
  },
})
</script>

<template>
  <a-carousel autoplay arrows dots-class="slick-dots slick-thumb">
    <template #customPaging="props">
      <a>
        <img :src="images[props.i]" />
      </a>
    </template>
    <div v-for="(image, index) in images" :key="index">
      <img :src="image" />
    </div>
  </a-carousel>
</template>

<style scoped>
:deep(.slick-dots) {
  position: relative;
  height: auto;
}

:deep(.slick-slide img) {
  border: 5px solid #fff;
  display: block;
  margin: auto;
  max-width: 80%;
  max-height: 60vh;
}

:deep(.slick-arrow) {
  display: none !important;
}

:deep(.slick-thumb) {
  bottom: 0px;
}

:deep(.slick-thumb li) {
  width: 60px;
  height: 45px;
}

:deep(.slick-thumb li img) {
  width: 100%;
  height: 100%;
  filter: grayscale(100%);
  display: block;
}

:deep .slick-thumb li.slick-active img {
  filter: grayscale(0%);
}
</style>