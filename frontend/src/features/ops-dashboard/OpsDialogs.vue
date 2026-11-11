<template>
  <el-dialog v-model="alertDeliveryDialog.visible" title="Fake-send ops alerts" width="680px">
    <el-alert class="delivery-warning" type="warning" title="local outbox only" :closable="false" show-icon>
      该操作只会调用 fake-send 合同并写入 audit，不会发送外部通知。
    </el-alert>
    <el-form label-position="top">
      <el-form-item label="Selected alert codes">
        <el-input :model-value="selectedActiveAlertCodes.join('\n')" type="textarea" :rows="4" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Reason">
        <el-input v-model="alertDeliveryDialog.reason" type="textarea" :rows="2" placeholder="说明为什么记录本次 fake delivery" />
      </el-form-item>
      <el-form-item label="Confirmation phrase">
        <el-input v-model="alertDeliveryDialog.confirmation" :placeholder="alertDeliveryConfirmationPhrase" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="alertDeliveryDialog.visible = false">取消</el-button>
      <el-button
        type="warning"
        :icon="Bell"
        :disabled="!canFakeSendAlertDelivery"
        :loading="alertDeliveryLoading"
        @click="fakeSendAlertDelivery"
      >
        确认 fake-send
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="realAlertDeliveryDialog.visible" title="Phase 7 Slack real-send" width="720px">
    <el-alert class="delivery-warning" type="error" title="controlled external delivery" :closable="false" show-icon>
      后端只允许固定 destination 和 alert code；secret value 不会显示在页面或 audit details 中。
    </el-alert>
    <el-form label-position="top">
      <el-form-item label="Destination">
        <el-input :model-value="REAL_ALERT_DELIVERY_DESTINATION_ID" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Alert code">
        <el-input :model-value="REAL_ALERT_DELIVERY_ALERT_CODE" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Reason">
        <el-input
          v-model="realAlertDeliveryDialog.reason"
          type="textarea"
          :rows="2"
          placeholder="说明为什么执行 Phase 7 Slack webhook pilot"
        />
      </el-form-item>
      <el-form-item label="Confirmation phrase">
        <el-input v-model="realAlertDeliveryDialog.confirmation" :placeholder="REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="realAlertDeliveryDialog.visible = false">取消</el-button>
      <el-button
        type="danger"
        :icon="Bell"
        :disabled="!canRealSendAlertDelivery"
        :loading="alertDeliveryLoading"
        @click="realSendAlertDelivery"
      >
        确认 real-send
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="providerCancellationDialog.visible" title="Fake-cancel provider operation" width="720px">
    <el-alert class="delivery-warning" type="warning" title="fake provider cancellation only" :closable="false" show-icon>
      该操作只会调用 fake-cancel 合同并写入 audit；不会调用 MinerU cancellation，也不会修改本地任务或队列。
    </el-alert>
    <el-form label-position="top">
      <el-form-item label="Target">
        <el-input :model-value="providerCancellationDialogTarget" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Provider Operation">
        <el-input :model-value="providerCancellationDialogOperation" readonly class="mono" />
      </el-form-item>
      <el-form-item label="Reason">
        <el-input
          v-model="providerCancellationDialog.reason"
          type="textarea"
          :rows="2"
          placeholder="说明为什么记录本次 provider fake cancellation"
        />
      </el-form-item>
      <el-form-item label="Confirmation phrase">
        <el-input v-model="providerCancellationDialog.confirmation" :placeholder="providerCancellationConfirmationPhrase" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="providerCancellationDialog.visible = false">取消</el-button>
      <el-button
        type="warning"
        :icon="CircleClose"
        :disabled="!canFakeCancelProviderCancellation"
        :loading="providerCancellationLoading"
        @click="fakeCancelProviderCancellation"
      >
        确认 fake-cancel
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// fake-send、real-send 与 fake-cancel 三个确认对话框。
import type { UnwrapRef } from "vue";
import { Bell, CircleClose } from "@element-plus/icons-vue";
import { REAL_ALERT_DELIVERY_DESTINATION_ID, REAL_ALERT_DELIVERY_ALERT_CODE, REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE } from "./opsDashboardFormat";
import type { OpsAlertDelivery } from "./useOpsAlertDelivery";
import type { ProviderCancellation } from "./useProviderCancellation";

const {
  alertDeliveryDialog,
  selectedActiveAlertCodes,
  alertDeliveryConfirmationPhrase,
  canFakeSendAlertDelivery,
  alertDeliveryLoading,
  fakeSendAlertDelivery,
  realAlertDeliveryDialog,
  canRealSendAlertDelivery,
  realSendAlertDelivery,
  providerCancellationDialog,
  providerCancellationDialogTarget,
  providerCancellationDialogOperation,
  providerCancellationConfirmationPhrase,
  canFakeCancelProviderCancellation,
  providerCancellationLoading,
  fakeCancelProviderCancellation,
} = defineProps<{
  alertDeliveryDialog: UnwrapRef<OpsAlertDelivery["alertDeliveryDialog"]>;
  selectedActiveAlertCodes: UnwrapRef<OpsAlertDelivery["selectedActiveAlertCodes"]>;
  alertDeliveryConfirmationPhrase: UnwrapRef<OpsAlertDelivery["alertDeliveryConfirmationPhrase"]>;
  canFakeSendAlertDelivery: UnwrapRef<OpsAlertDelivery["canFakeSendAlertDelivery"]>;
  alertDeliveryLoading: UnwrapRef<OpsAlertDelivery["alertDeliveryLoading"]>;
  fakeSendAlertDelivery: UnwrapRef<OpsAlertDelivery["fakeSendAlertDelivery"]>;
  realAlertDeliveryDialog: UnwrapRef<OpsAlertDelivery["realAlertDeliveryDialog"]>;
  canRealSendAlertDelivery: UnwrapRef<OpsAlertDelivery["canRealSendAlertDelivery"]>;
  realSendAlertDelivery: UnwrapRef<OpsAlertDelivery["realSendAlertDelivery"]>;
  providerCancellationDialog: UnwrapRef<ProviderCancellation["providerCancellationDialog"]>;
  providerCancellationDialogTarget: UnwrapRef<ProviderCancellation["providerCancellationDialogTarget"]>;
  providerCancellationDialogOperation: UnwrapRef<ProviderCancellation["providerCancellationDialogOperation"]>;
  providerCancellationConfirmationPhrase: UnwrapRef<ProviderCancellation["providerCancellationConfirmationPhrase"]>;
  canFakeCancelProviderCancellation: UnwrapRef<ProviderCancellation["canFakeCancelProviderCancellation"]>;
  providerCancellationLoading: UnwrapRef<ProviderCancellation["providerCancellationLoading"]>;
  fakeCancelProviderCancellation: UnwrapRef<ProviderCancellation["fakeCancelProviderCancellation"]>;
}>();
</script>

<style scoped lang="scss">
.delivery-warning {
  margin-bottom: var(--app-space-4);
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}
</style>
