<template>
  <div>
    <h3>Main App</h3>
    <Content />
  </div>
</template>

<script>
import { ref, defineAsyncComponent } from "vue";
// import Content from "./components/Content";
export default {
  components: {
    Content: defineAsyncComponent(() => import("./components/Content")),
  },
  // components: {
  //   Content,
  // },
  setup() {
    const count = ref(0);
    const inc = () => {
      count.value++;
    };

    return {
      count,
      inc,
    };
  },
};
</script>

<style scoped>
img {
  width: 200px;
}
h1 {
  font-family: Arial, Helvetica, sans-serif;
}
</style>
