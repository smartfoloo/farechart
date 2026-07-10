import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { loadMeta } from './lib/data.js';

const target = document.getElementById('app');

loadMeta().then((meta) => mount(App, { target, props: { meta } }));
