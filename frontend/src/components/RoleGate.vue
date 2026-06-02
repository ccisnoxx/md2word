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
  }>(),
  {
    roles: () => ["admin"],
  },
);

const auth = useAuthStore();
const allowed = computed(() => Boolean(auth.user?.role && props.roles.includes(auth.user.role)));
</script>
