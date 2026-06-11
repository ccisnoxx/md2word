<!-- frontend/src/components/RoleGate.vue: Gate admin-only controls by the current user's role. -->
<template>
  <slot v-if="allowed" />
</template>

<script setup lang="ts">
import { computed } from "vue";

import { useAuthStore } from "@/stores/auth";

const props = withDefaults(
  defineProps<{
    roles?: string[];
    permissions?: string[];
  }>(),
  {
    roles: () => ["admin"],
    permissions: () => [],
  },
);

const auth = useAuthStore();
const allowed = computed(() => {
  if (props.permissions.length > 0) {
    return props.permissions.every((permission) => auth.hasPermission(permission));
  }
  return props.roles.some((role) => auth.hasRole(role));
});
</script>
