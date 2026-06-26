module.exports = {
  apps: [
    {
      name: "calkulator",
      script: "web.py",
      interpreter: "python3",
      // Автоперезапуск при падении
      autorestart: true,
      // Перезапускать не более 10 раз за 30 секунд (защита от crash-loop)
      max_restarts: 10,
      min_uptime: "30s",
      // Перезапуск при превышении 200 МБ памяти
      max_memory_restart: "200M",
      // Переменные окружения (лучше хранить в .env, а не здесь)
      env: {
        NODE_ENV: "production",
        PORT: 5000,
      },
      // Логи
      out_file: "logs/web-out.log",
      error_file: "logs/web-err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
    },
  ],
};
