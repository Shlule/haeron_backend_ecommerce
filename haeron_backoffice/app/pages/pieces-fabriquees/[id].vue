<script setup lang="ts">
/*
 * Fiche d'une pièce fabriquée : modèle, options, lot, instrument sur lequel elle est montée,
 * description modifiable et historique.
 */
import type { PartSheet, ProductionForm } from '~/utils/production'
import { NAlert, NButton, NInput, NSpin, NTag, useMessage } from 'naive-ui'

const route = useRoute()
const message = useMessage()
const partId = computed(() => String(route.params.id))

const sheet = ref<PartSheet | null>(null)
const eventTypes = ref<ProductionForm['eventTypes']>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const description = ref('')

useHead(() => ({ title: `Pièce ${sheet.value?.serialNumber ?? ''} · Haeron Back-office` }))

async function load() {
  loading.value = true
  loadError.value = null
  try {
    const { backoffice } = await gql<{ backoffice: { partSheet: PartSheet | null, historyEventTypes: ProductionForm['eventTypes'] } }>(
      'query ($id: UUID!) { backoffice { partSheet(partId: $id) historyEventTypes } }',
      { id: partId.value },
    )
    sheet.value = backoffice.partSheet
    eventTypes.value = backoffice.historyEventTypes
    description.value = sheet.value?.description ?? ''
  }
  catch (e) {
    loadError.value = errorText(e)
  }
  finally {
    loading.value = false
  }
}
onMounted(load)

function print() {
  window.print()
}

const saving = ref(false)
async function save() {
  saving.value = true
  try {
    const { backoffice } = await gql<{ backoffice: { updatePartInfo: PartSheet } }>(
      'mutation ($id: UUID!, $description: String!) { backoffice { updatePartInfo(partId: $id, description: $description) } }',
      { id: partId.value, description: description.value },
    )
    sheet.value = backoffice.updatePartInfo
    description.value = sheet.value.description
    message.success('Pièce enregistrée')
  }
  catch (e) {
    message.error(errorText(e))
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <NuxtLink to="/pieces-fabriquees" class="text-xs text-white/50 tracking-[0.2em] font-mono uppercase hover:text-white print:hidden">
      ← Pièces fabriquées
    </NuxtLink>

    <NAlert v-if="loadError" type="error" class="mt-4">
      {{ loadError }}
      <NButton size="small" class="ml-3" @click="load">
        Réessayer
      </NButton>
    </NAlert>

    <NSpin :show="loading" class="mt-4">
      <p v-if="!loading && !sheet && !loadError" class="text-white/50 py-10 text-center">
        Cette pièce est introuvable.
      </p>

      <template v-if="sheet">
        <div class="mb-8 flex flex-wrap gap-4 items-end justify-between">
          <div>
            <h1 class="text-3xl font-semibold m-0 flex gap-3 items-center">
              {{ sheet.partModel.name }} <span class="font-mono">{{ sheet.serialNumber }}</span>
              <NTag v-if="sheet.isMaster" type="info" :bordered="false">
                Maîtresse
              </NTag>
            </h1>
            <p class="text-sm text-white/50 m-0 mt-1">
              {{ label(sheet.partType) }} · {{ sheet.partModel.code }} · lot {{ sheet.batch.name }} ({{ sheet.batch.code }})
              · fabriquée le {{ dateTimeFormat.format(new Date(sheet.createdAt)) }}
            </p>
          </div>
          <div class="flex flex-wrap gap-3 items-center">
            <SaleStatus
              target="part"
              :target-id="sheet.id"
              :status="sheet.status"
              :sold-at="sheet.soldAt"
              @changed="(value) => (sheet = value as PartSheet)"
            />
            <NButton class="print:hidden" @click="print">
              Imprimer la fiche
            </NButton>
          </div>
        </div>

        <div class="mb-10 gap-4 grid sm:grid-cols-3">
          <section class="p-4 border border-white/10 rounded-xl">
            <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-3 uppercase">
              Options
            </h2>
            <div v-for="option in sheet.options" :key="option.option" class="text-sm">
              <span class="text-white/50">{{ label(option.option) }} :</span> {{ label(option.value) }}
            </div>
            <p v-if="!sheet.options.length" class="text-sm text-white/40 m-0">
              Aucune option précisée.
            </p>
          </section>
          <section class="p-4 border border-white/10 rounded-xl">
            <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-3 uppercase">
              Instrument
            </h2>
            <NuxtLink v-if="sheet.instrument" :to="`/instruments/${sheet.instrument.id}`" class="text-sm hover:underline">
              {{ sheet.instrument.model }} →
            </NuxtLink>
            <p v-else class="text-sm text-white/40 m-0">
              Non montée
            </p>
          </section>
          <section class="p-4 border border-white/10 rounded-xl">
            <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-3 uppercase">
              Propriétaire
            </h2>
            <p class="text-sm m-0">
              {{ sheet.owner ?? '—' }}
            </p>
          </section>
        </div>

        <section class="mb-10 p-5 border border-white/10 rounded-xl">
          <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-2 uppercase">
            Description
          </h2>
          <NInput v-model:value="description" type="textarea" :autosize="{ minRows: 3, maxRows: 12 }" placeholder="Aucune description" class="mb-3 print:hidden" />
          <p class="m-0 hidden whitespace-pre-line print:block">
            {{ sheet.description }}
          </p>
          <NButton type="primary" :disabled="description === sheet.description" :loading="saving" class="print:hidden" @click="save">
            Enregistrer
          </NButton>
        </section>

        <h2 class="text-lg font-semibold m-0 mb-4">
          Historique
        </h2>
        <HistoryTimeline v-model="sheet.history" target="part" :target-id="sheet.id" :event-types="eventTypes" />
      </template>
    </NSpin>
  </div>
</template>
