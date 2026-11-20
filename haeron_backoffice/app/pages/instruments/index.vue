<script setup lang="ts">
/*
 * Instruments fabriqués, les plus récents d'abord. Recherche par numéro de série d'une pièce,
 * modèle, propriétaire ou description. Chaque ligne ouvre la fiche de l'instrument.
 */
import { NAlert, NButton, NInput, NSelect, NSpin, NTag } from 'naive-ui'

useHead({ title: 'Instruments · Haeron Back-office' })

interface InstrumentRow {
  id: string
  serialNumber: string
  model: string
  instrumentType: string
  owner: string | null
  description: string
  partCount: number
  status: string
  createdAt: string
}

const PAGE = 50
const route = useRoute()
const router = useRouter()
const search = ref((route.query.q as string) || '')

// filtre de statut dans l'URL, comme la recherche
const status = computed(() => (route.query.statut as string) || null)
const statusFilter = [{ value: '', label: 'Tous les statuts' }, ...saleStatusOptions.map(s => ({ value: s.value, label: s.label }))]
function setStatus(value: string | null) {
  router.replace({ query: { ...route.query, statut: value || undefined } })
}
watch(status, () => load())

const rows = ref<InstrumentRow[]>([])
const totalCount = ref(0)
const loading = ref(true)
const loadError = ref<string | null>(null)

async function load(append = false) {
  loading.value = true
  loadError.value = null
  try {
    const { backoffice } = await gql<{ backoffice: { instruments: { totalCount: number, results: InstrumentRow[] } } }>(
      'query ($offset: Int!, $limit: Int!, $search: String, $status: String) { backoffice { instruments(offset: $offset, limit: $limit, search: $search, status: $status) } }',
      { offset: append ? rows.value.length : 0, limit: PAGE, search: search.value.trim() || null, status: status.value },
    )
    rows.value = append ? [...rows.value, ...backoffice.instruments.results] : backoffice.instruments.results
    totalCount.value = backoffice.instruments.totalCount
  }
  catch (e) {
    loadError.value = errorText(e)
  }
  finally {
    loading.value = false
  }
}

onMounted(() => load())

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
          Instruments
        </h1>
        <p class="text-sm text-white/50 m-0 mt-1">
          Les instruments assemblés à l'atelier, avec leurs pièces et leur historique.
        </p>
      </div>
      <div class="flex flex-wrap gap-3 items-center">
        <NSelect :value="status ?? ''" :options="statusFilter" class="!w-44" @update:value="setStatus" />
        <NInput v-model:value="search" clearable placeholder="N° de série, modèle, propriétaire" class="!w-72" />
        <NButton type="primary" @click="navigateTo('/instruments/nouveau')">
          Nouvel instrument
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
        {{ search || status ? 'Aucun instrument ne correspond.' : 'Aucun instrument pour le moment.' }}
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
                Propriétaire
              </th>
              <th class="font-normal px-4 py-3 text-right">
                Pièces
              </th>
              <th class="font-normal px-4 py-3">
                Statut
              </th>
              <th class="font-normal px-4 py-3">
                Assemblé le
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.id"
              class="border-t border-white/10 cursor-pointer hover:bg-white/[0.04]"
              @click="navigateTo(`/instruments/${row.id}`)"
            >
              <td class="px-4 py-3">
                <NuxtLink :to="`/instruments/${row.id}`" class="font-mono hover:underline" @click.stop>
                  {{ row.serialNumber }}
                </NuxtLink>
                <div v-if="row.description" class="text-xs text-white/40 max-w-80 truncate">
                  {{ row.description }}
                </div>
              </td>
              <td class="px-4 py-3">
                {{ row.model }}
                <div class="text-xs text-white/40">
                  {{ label(row.instrumentType) }}
                </div>
              </td>
              <td class="text-white/60 px-4 py-3">
                {{ row.owner ?? '—' }}
              </td>
              <td class="px-4 py-3 text-right">
                {{ row.partCount }}
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
          Afficher plus ({{ totalCount - rows.length }} restants)
        </NButton>
      </div>
    </NSpin>
  </div>
</template>
