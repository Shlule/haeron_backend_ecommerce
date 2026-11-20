<script setup lang="ts">
/*
 * Fiche d'un instrument : description et propriétaire modifiables, composition (chaque pièce avec
 * son numéro, son modèle et ses options), configuration d'origine, et historique de l'instrument et de ses pièces.
 */
import type { InstrumentSheet, ProductionForm } from '~/utils/production'
import { NAlert, NButton, NInput, NSpin, NTag, useMessage } from 'naive-ui'

const route = useRoute()
const message = useMessage()
const instrumentId = computed(() => String(route.params.id))

const sheet = ref<InstrumentSheet | null>(null)
const eventTypes = ref<ProductionForm['eventTypes']>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

useHead(() => ({ title: `Instrument ${sheet.value?.serialNumber ?? ''} · Haeron Back-office` }))

const description = ref('')
const ownerEmail = ref('')

async function load() {
  loading.value = true
  loadError.value = null
  try {
    // la fiche et les types d'événement en une seule requête
    const { backoffice } = await gql<{ backoffice: { instrumentSheet: InstrumentSheet | null, historyEventTypes: ProductionForm['eventTypes'] } }>(
      'query ($id: UUID!) { backoffice { instrumentSheet(instrumentId: $id) historyEventTypes } }',
      { id: instrumentId.value },
    )
    sheet.value = backoffice.instrumentSheet
    eventTypes.value = backoffice.historyEventTypes
    description.value = sheet.value?.description ?? ''
    ownerEmail.value = sheet.value?.owner ?? ''
  }
  catch (e) {
    loadError.value = errorText(e)
  }
  finally {
    loading.value = false
  }
}
onMounted(load)

const changed = computed(() => !!sheet.value && (description.value !== sheet.value.description || ownerEmail.value.trim() !== (sheet.value.owner ?? '')))

const saving = ref(false)
async function save() {
  if (!sheet.value)
    return
  saving.value = true
  try {
    const { backoffice } = await gql<{ backoffice: { updateInstrumentInfo: InstrumentSheet } }>(
      'mutation ($id: UUID!, $description: String, $owner: String) { backoffice { updateInstrumentInfo(instrumentId: $id, description: $description, ownerEmail: $owner) } }',
      { id: instrumentId.value, description: description.value, owner: ownerEmail.value.trim() },
    )
    sheet.value = backoffice.updateInstrumentInfo
    description.value = sheet.value.description
    ownerEmail.value = sheet.value.owner ?? ''
    message.success('Instrument enregistré')
  }
  catch (e) {
    message.error(errorText(e))
  }
  finally {
    saving.value = false
  }
}

function print() {
  window.print()
}
</script>

<template>
  <div>
    <NuxtLink to="/instruments" class="text-xs text-white/50 tracking-[0.2em] font-mono uppercase hover:text-white print:hidden">
      ← Instruments
    </NuxtLink>

    <NAlert v-if="loadError" type="error" class="mt-4">
      {{ loadError }}
      <NButton size="small" class="ml-3" @click="load">
        Réessayer
      </NButton>
    </NAlert>

    <NSpin :show="loading" class="mt-4">
      <p v-if="!loading && !sheet && !loadError" class="text-white/50 py-10 text-center">
        Cet instrument est introuvable.
      </p>

      <template v-if="sheet">
        <div class="mb-8 flex flex-wrap gap-4 items-end justify-between">
          <div>
            <h1 class="text-3xl font-semibold m-0">
              {{ sheet.model }} <span class="font-mono">{{ sheet.serialNumber }}</span>
            </h1>
            <p class="text-sm text-white/50 m-0 mt-1">
              {{ label(sheet.instrumentType) }} · assemblé le {{ dateTimeFormat.format(new Date(sheet.createdAt)) }}
              <template v-if="sheet.configuration?.source === 'order'">
                · d'après la commande
                <NuxtLink :to="`/commandes/${sheet.configuration.orderId}`" class="font-mono hover:underline">
                  {{ sheet.configuration.reference }}
                </NuxtLink>
                ({{ sheet.configuration.product }})
              </template>
            </p>
          </div>
          <div class="flex flex-wrap gap-3 items-center">
            <SaleStatus
              target="instrument"
              :target-id="sheet.id"
              :status="sheet.status"
              :sold-at="sheet.soldAt"
              @changed="(value) => (sheet = value as InstrumentSheet)"
            />
            <NButton class="print:hidden" @click="print">
              Imprimer la fiche
            </NButton>
          </div>
        </div>

        <section class="mb-10 p-5 border border-white/10 rounded-xl">
          <div class="mb-4 gap-4 grid sm:grid-cols-[1fr_20rem]">
            <div>
              <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-2 uppercase">
                Description
              </h2>
              <NInput v-model:value="description" type="textarea" :autosize="{ minRows: 3, maxRows: 12 }" placeholder="Aucune description" class="print:hidden" />
              <p class="m-0 hidden whitespace-pre-line print:block">
                {{ sheet.description }}
              </p>
            </div>
            <div>
              <h2 class="text-xs text-white/40 tracking-[0.15em] font-mono m-0 mb-2 uppercase">
                Propriétaire
              </h2>
              <NInput v-model:value="ownerEmail" placeholder="E-mail du compte client" class="print:hidden" />
              <p class="m-0 hidden print:block">
                {{ sheet.owner ?? '—' }}
              </p>
            </div>
          </div>
          <NButton type="primary" :disabled="!changed" :loading="saving" class="print:hidden" @click="save">
            Enregistrer
          </NButton>
        </section>

        <h2 class="text-lg font-semibold m-0 mb-4">
          Composition
        </h2>
        <div class="mb-10 border border-white/10 rounded-xl overflow-x-auto">
          <table class="text-sm w-full border-collapse">
            <thead>
              <tr class="text-xs text-white/40 tracking-[0.15em] font-mono text-left uppercase">
                <th class="font-normal px-4 py-3">
                  Pièce
                </th>
                <th class="font-normal px-4 py-3">
                  N° de série
                </th>
                <th class="font-normal px-4 py-3">
                  Options
                </th>
                <th class="font-normal px-4 py-3">
                  Lot
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="part in sheet.parts" :key="part.id" class="align-top border-t border-white/10">
                <td class="px-4 py-3">
                  <div class="flex gap-2 items-center">
                    {{ part.partModel.name }}
                    <NTag v-if="part.isMaster" size="tiny" type="info" :bordered="false">
                      Maîtresse
                    </NTag>
                  </div>
                  <div class="text-xs text-white/40">
                    {{ label(part.partType) }} · {{ part.partModel.code }}
                  </div>
                  <p v-if="part.description" class="text-xs text-white/60 m-0 mt-1 whitespace-pre-line">
                    {{ part.description }}
                  </p>
                </td>
                <td class="px-4 py-3">
                  <NuxtLink :to="`/pieces-fabriquees/${part.id}`" class="font-mono hover:underline">
                    {{ part.serialNumber }}
                  </NuxtLink>
                </td>
                <td class="px-4 py-3">
                  <div v-for="option in part.options" :key="option.option">
                    <span class="text-white/50">{{ label(option.option) }} :</span> {{ label(option.value) }}
                  </div>
                  <span v-if="!part.options.length" class="text-white/40">—</span>
                </td>
                <td class="text-white/60 font-mono px-4 py-3">
                  {{ part.batch.code }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <h2 class="text-lg font-semibold m-0 mb-4">
          Historique
        </h2>
        <HistoryTimeline v-model="sheet.history" target="instrument" :target-id="sheet.id" :event-types="eventTypes" />
      </template>
    </NSpin>
  </div>
</template>
