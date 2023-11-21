import { createApp, defineAsyncComponent } from 'vue';
import Layout from './Layout.vue';

const Content = defineAsyncComponent(() => import('home/Content'));

const app = createApp(Layout);

app.component('content-element', Content);

app.mount('#app');
