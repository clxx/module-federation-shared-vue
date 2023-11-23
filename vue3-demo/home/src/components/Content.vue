<template>
  <p id="remoteVersion" style="color: red;">{{ version }}</p>
  <p id="sameInstance">{{ sameInstance }}</p>
</template>

<script setup>
import { createApp, onMounted, version } from 'vue';

if (!window.layoutCreateApp) {
  throw "No layoutCreateApp!";
}

const sameInstance = createApp === window.layoutCreateApp;
</script>
