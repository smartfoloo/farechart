<script>
  import { fareGradient } from './fare.js';

  let { t, min, max } = $props();
</script>

<div class="legend">
  <div class="title">{t.fareScale}</div>
  <div class="ramp" style="background: {fareGradient()}"></div>
  <div class="ends">
    <span>¥{min}</span><span>¥{max}</span>
  </div>
</div>

<style>
  .legend {
    position: absolute;
    top: 20px;
    right: 20px;
    width: 190px;
    z-index: 6;
    background: #fff;
    border-radius: 12px;
    border: 1px solid var(--line);
    box-shadow: var(--shadow-panel);
    padding: 12px 14px 13px;
  }
  .title {
    font-weight: 500;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 8px;
  }
  .ramp {
    height: 10px;
    border-radius: 6px;
  }
  .ends {
    display: flex;
    justify-content: space-between;
    margin-top: 5px;
    font-size: 11px;
    color: var(--muted-2);
  }
</style>
