<script setup lang="ts">
/*
 * Pièces fabriquées, les plus récentes d'abord : numéro de série, modèle, options, instrument sur lequel
 * elles sont montées. Filtre « non montées » pour retrouver les pièces disponibles.
 */
import type { PartRow } from '~/utils/production'
import { NAlert, NButton, NCheckbox, NInput, NSelect, NSpin, NTag } from 'naive-ui'

useHead({ title: 'Pièces fabriquées · Haeron Back-office' })

const PAGE = 50
const route = useRoute()
const router = useRouter()
const search = ref((route.query.q as string) || '')
const freeOnly = ref(route.query.libres === '1')

// filtre de statut dans l'URL, comme la recherche
const status = computed(() => (route.query.statut as string) || null)
const statusFilter = [{ value: '', label: 'Tous les statuts' }, ...saleStatusOptions.map(s => ({ value: s.value, label: s.label }))]
function setStatus(value: string | null) {
  router.replace({ query: { ...route.query, statut: value || undefined } })
}
watch(status, () => load())

const rows = ref<PartRow[]>([])
const totalCount = ref(0)
const loading = ref(true)
const loadError = ref<string | null>(null)

async function load(append = false) {
  loading.value = true
  loadError.value = null
  try {
    const { backoffice } = await gql<{ backoffice: { producedParts: { totalCount: number, results: PartRow[] } } }>(
      'query ($offset: Int!, $limit: Int!, $search: String, $free: Boolean!, $status: String) { backoffice { producedParts(offset: $offset, limit: $limit, search: $search, freeOnly: $free, status: $status) } }',
      { offset: append ? rows.value.length : 0, limit: PAGE, search: search.value.trim() || null, free: freeOnly.value, status: status.value },
    )
    rows.value = append ? [...rows.value, ...backoffice.producedParts.results] : backoffice.producedParts.results
    totalCount.value = backoffice.producedParts.totalCount
  }
  catch (e) {
    loadError.value = errorText(e)
  }
  finally {
    loading.value = false
  }
}

onMounted(() => load())

watch(freeOnly, (value) => {
  router.replace({ query: { ...route.query, libres: value ? '1' : undefined } })
  load()
})

let timer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    router.replace({ query: { ...route.query, q: value.trim() || undefined } })
    load()
  }, 300)
})
</script>

<template>
  <div>
    <div class="mb-6 flex flex-wrap gap-4 items-end justify-between">
      <div>
        <h1 class="text-3xl font-semibold m-0">
          Pièces fabriquées
        </h1>
        <p class="text-sm text-white/50 m-0 mt-1">
          Chaque pièce sortie de l'atelier, avec son numéro de série, ses options et son historique.
        </p>
      </div>
      <div class="flex flex-wrap gap-3 items-center">
        <NCheckbox v-model:checked="freeOnly">
          Non montées
        </NCheckbox>
        <NSelect :value="status ?? ''" :options="statusFilter" class="!w-44" @update:value="setStatus" />
        <NInput v-model:value="search" clearable placeholder="N° de série, modèle, description" class="!w-72" />
        <NButton type="primary" @click="navigateTo('/pieces-fabriquees/nouvelle')">
          Nouvelle pièce
        </NButton>
      </div>
    </div>

    <NAlert v-if="loadError" type="error" class="mb-6">
      {{ loadError }}
      <NButton size="small" class="ml-3" @click="load()">
        Réessayer
      </NButton>
    </NAlert>

    <NSpin :show="loading && !rows.length">
      <p v-if="!loading && !rows.length && !loadError" class="text-white/50 py-10 text-center">
        {{ search || freeOnly || status ? 'Aucune pièce ne correspond.' : 'Aucune pièce fabriquée pour le moment.' }}
      </p>

      <div v-else class="border border-white/10 rounded-xl overflow-x-auto">
        <table class="text-sm w-full border-collapse">
          <thead>
            <tr class="text-xs text-white/40 tracking-[0.15em] font-mono text-left uppercase">
              <th class="font-normal px-4 py-3">
                N° de série
              </th>
              <th class="font-normal px-4 py-3">
                Modèle
              </th>
              <th class="font-normal px-4 py-3">
                Options
              </th>
              <th class="font-normal px-4 py-3">
                Instrument
              </th>
              <th class="font-normal px-4 py-3">
                Statut
              </th>
              <th class="font-normal px-4 py-3">
                Fabriquée le
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.id"
              class="align-top border-t border-white/10 cursor-pointer hover:bg-white/[0.04]"
              @click="navigateTo(`/pieces-fabriquees/${row.id}`)"
            >
              <td class="px-4 py-3">
                <NuxtLink :to="`/pieces-fabriquees/${row.id}`" class="font-mono hover:underline" @click.stop>
                  {{ row.serialNumber }}
                </NuxtLink>
                <NTag v-if="row.isMaster" size="tiny" type="info" :bordered="false" class="ml-2">
                  Maîtresse
                </NTag>
              </td>
              <td class="px-4 py-3">
                {{ row.partModel.name }}
                <div class="text-xs text-white/40">
                  {{ label(row.partType) }} · {{ row.partModel.code }}
                </div>
              </td>
              <td class="text-white/70 px-4 py-3">
                {{ row.options.map(o => label(o.value)).join(', ') || '—' }}
              </td>
              <td class="px-4 py-3">
                <NuxtLink v-if="row.instrument" :to="`/instruments/${row.instrument.id}`" class="hover:underline" @click.stop>
                  {{ row.instrument.model }}
                </NuxtLink>
                <span v-else class="text-white/40">Non montée</span>
              </td>
              <td class="px-4 py-3">
                <NTag size="small" :type="saleStatusOf(row.status).type" :bordered="false">
                  {{ saleStatusOf(row.status).label }}
                </NTag>
              </td>
              <td class="text-white/60 px-4 py-3 whitespace-nowrap">
                {{ dateTimeFormat.format(new Date(row.createdAt)) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="rows.length < totalCount" class="mt-4 text-center">
        <NButton :loading="loading" @click="load(true)">
          Afficher plus ({{ totalCount - rows.length }} restantes)
        </NButton>
      </div>
    </NSpin>
  </div>
</template>
