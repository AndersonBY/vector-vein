<script setup>
import { useI18n } from 'vue-i18n'
import { CloseOne, Search } from '@icon-park/vue-next'

const searchText = defineModel()
const { t } = useI18n()
const emit = defineEmits(['search', 'clear-search'])

const search = () => {
	emit('search')
}

const clearSearch = () => {
	searchText.value = ''
	emit('clear-search')
}
</script>

<template>
	<a-input v-model:value="searchText" :placeholder="t('components.inputSearch.input_search_text')" @press-enter="search"
		class="search-input">
		<template #prefix>
			<Search />
		</template>
		<template #suffix>
			<CloseOne class="clear-search-button" theme="filled" @click="clearSearch" style="cursor: pointer;"
				v-if="searchText.length > 0" />
		</template>
	</a-input>
</template>

<style scoped>
.search-input {
	max-width: 250px;
}

.clear-search-button {
	margin-right: 4px;
}

.clear-search-button:hover {
	color: #28c5e5;
}
</style>