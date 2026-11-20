<script setup lang="ts">
/*
 * Statut de vente d'un instrument ou d'une pièce : en stock, réservé, vendu.
 * Le changement est écrit dans l'historique, avec la note si elle est remplie ;
 * sur un instrument, ses pièces prennent le même statut.
 */
import { NButton, NInput, NSelect, NTag, useMessage } from 'naive-ui'

const props = defineProps<{ target: 'instrument' | 'part', targetId: string, status: string, soldAt: string | null }>()
// la fiche à jour (instrument ou pièce) renvoyée par le backend
const emit = defineEmits<{ changed: [sheet: unknown] }>()

const message = useMessage()
const next = ref(props.status)
const note = ref('')
const saving = ref(false)
watch(() => props.status, (value) => {
  next.value = value
})

async function save() {
  saving.value = true
  try {
    const { backoffice } = await gql<{ backoffice: { setProductionStatus: unknown } }>(
      'mutation ($t: String!, $id: UUID!, $s: String!, $n: String!) { backoffice { setProductionStatus(target: $t, targetId: $id, status: $s, note: $n) } }',
      { t: props.target, id: props.targetId, s: next.value, n: note.value },
    )
    note.value = ''
    emit('changed', backoffice.setProductionStatus)
    message.success(`Statut : ${saleStatusOf(next.value).label}`)
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
  <div class="flex flex-wrap gap-2 items-center">
    <!-- le menu montre le statut ; la date de vente s'ajoute à côté -->
    <span v-if="status === 'sold' && soldAt" class="text-sm text-white/50">
      Vendu le {{ dateTimeFormat.format(new Date(soldAt)) }}
    </span>
    <NTag :type="saleStatusOf(status).type" :bordered="false" class="hidden print:inline-flex">
      {{ saleStatusOf(status).label }}
    </NTag>
    <NSelect v-model:value="next" :options="saleStatusOptions" class="!w-36 print:hidden" />
    <template v-if="next !== status">
      <NInput v-model:value="note" placeholder="Note pour l'historique (facultatif)" class="!w-72 print:hidden" />
      <NButton type="primary" :loading="saving" class="print:hidden" @click="save">
        Changer
      </NButton>
    </template>
  </div>
</template>
