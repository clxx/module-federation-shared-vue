<template>
  <p id="remoteVersion" style="color: red;">remoteVersion: {{ version }}</p>
  <p id="sameInstance">sameInstance: {{ sameInstance }}</p>
</template>

<script setup>
import { createApp, version } from 'vue';

if (!window.layoutCreateApp) {
  throw "No layoutCreateApp!";
}

const sameInstance = createApp === window.layoutCreateApp;
</script>
