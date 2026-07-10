<script>
  let { size = 13, color = 'currentColor' } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <path
    d="M12 20V13M12 13L6 7M12 13L18 7"
    stroke={color}
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  />
  <circle cx="12" cy="21" r="1.6" fill={color} />
  <circle cx="6" cy="6" r="1.6" fill={color} />
  <circle cx="18" cy="6" r="1.6" fill={color} />
</svg>
