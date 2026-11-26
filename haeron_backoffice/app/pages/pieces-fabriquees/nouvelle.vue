<script setup lang="ts">
/*
 * Nouvelle pièce fabriquée seule (pour le stock ou une réparation) : atelier, type d'instrument,
 * modèle, options et description. Le numéro de série est donné à l'enregistrement.
 */
import type { PartLine, ProductionForm } from '~/utils/production'
import { NAlert, NButton, NCheckbox, NFormItem, NInput, NSelect, NSpin, useMessage } from 'naive-ui'

useHead({ title: 'Nouvelle pièce · Haeron Back-office' })

const message = useMessage()

const form = ref<ProductionForm | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

const factoryId = ref<string | null>(null)
const instrumentTypeId = ref<string | null>(null)
const ownerEmail = ref('')
const isMaster = ref(false)
const saleStatus = ref('in_stock')
const line = ref<PartLine>({ key: 1, existingPartId: null, partModelId: null, optionIds: [], description: '' })

async function load() {
  loading.value = true
  loadError.value = null
  try {
    form.value = await loadProductionForm()
    if (form.value.factories.length === 1)
      factoryId.value = form.value.factories[0]!.id
    if (form.value.instrumentTypes.length === 1)
      instrumentTypeId.value = form.value.instrumentTypes[0]!.id
  }
  catch (e) {
    loadError.value = errorText(e)
  }
  finally {
    loading.value = false
  }
}
onMounted(load)

function onBatchCreated(partModelId: string, batch: { id: string, name: string, code: string }) {
  const model = form.value?.partModels.find(pm => pm.id === partModelId)
  if (model)
    model.activeBatch = batch
}

const missing = computed(() => {
  if (!factoryId.value || !instrumentTypeId.value)
    return 'Choisis l\'atelier et le type d\'instrument.'
  if (!line.value.partModelId)
    return 'Choisis le modèle de pièce.'
  if (!form.value?.partModels.find(pm => pm.id === line.value.partModelId)?.activeBatch)
    return 'Crée d\'abord un lot pour ce modèle.'
  return null
})

const saving = ref(false)
async function submit() {
  if (missing.value)
    return
  saving.value = true
  try {
    const { backoffice } = await gql<{ backoffice: { buildPart: { id: string, serialNumber: string } } }>(
      'mutation ($data: BoBuildPartInput!) { backoffice { buildPart(data: $data) } }',
      {
        data: {
          partModelId: line.value.partModelId,
          factoryId: factoryId.value,
          instrumentTypeId: instrumentTypeId.value,
          optionIds: line.value.optionIds,
          description: line.value.description,
          ownerEmail: ownerEmail.value.trim() || null,
          isMaster: isMaster.value,
          status: saleStatus.value,
        },
      },
    )
    message.success(`Pièce ${backoffice.buildPart.serialNumber} créée`)
    await navigateTo(`/pieces-fabriquees/${backoffice.buildPart.id}`)
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
    <NuxtLink to="/pieces-fabriquees" class="text-xs text-white/50 tracking-[0.2em] font-mono uppercase hover:text-white">
      ← Pièces fabriquées
    </NuxtLink>
    <h1 class="text-3xl font-semibold m-0 mb-8 mt-4">
      Nouvelle pièce
    </h1>

    <NAlert v-if="loadError" type="error" class="mb-6">
      {{ loadError }}
      <NButton size="small" class="ml-3" @click="load">
        Réessayer
      </NButton>
    </NAlert>

    <NSpin :show="loading">
      <form v-if="form" class="flex flex-col gap-8" @submit.prevent="submit">
        <section class="p-5 border border-white/10 rounded-xl">
          <div class="mb-4 gap-4 grid lg:grid-cols-4 sm:grid-cols-2">
            <NFormItem label="Atelier" :show-feedback="false">
              <NSelect v-model:value="factoryId" :options="form.factories.map(f => ({ value: f.id, label: `${f.name} (${f.code})` }))" placeholder="Choisir" />
            </NFormItem>
            <NFormItem label="Type d'instrument" :show-feedback="false">
              <NSelect v-model:value="instrumentTypeId" :options="form.instrumentTypes.map(t => ({ value: t.id, label: label(t.name) }))" placeholder="Choisir" />
            </NFormItem>
            <NFormItem label="Propriétaire (e-mail du compte client)" :show-feedback="false">
              <NInput v-model:value="ownerEmail" placeholder="Facultatif" />
            </NFormItem>
            <NFormItem label="Statut" :show-feedback="false">
              <NSelect v-model:value="saleStatus" :options="saleStatusOptions" />
            </NFormItem>
          </div>
          <NCheckbox v-model:checked="isMaster" class="mb-4">
            Pièce maîtresse (elle portera le numéro de l'instrument)
          </NCheckbox>
          <PartFields v-model="line" :part-models="form.partModels" @batch-created="onBatchCreated" />
        </section>

        <div class="flex gap-4 items-center">
          <NButton attr-type="submit" type="primary" size="large" :loading="saving" :disabled="!!missing">
            Créer la pièce
          </NButton>
          <span v-if="missing" class="text-sm text-white/50">{{ missing }}</span>
        </div>
      </form>
    </NSpin>
  </div>
</template>
