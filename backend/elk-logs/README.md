# Centralized Logging for GenAssist Containers

```bash
cd elk-logs
docker composer up -d
```
 This will start services:
  - elasticsearch
  - logstash
  - filebeat
  - kibana

**Kibana** - Open Search Logs UI: 

http://localhost:5601

## Kibaba vs. Grafana

| Feature                     | **Grafana**                             | **Kibana**                                    |
| --------------------------- | --------------------------------------- | --------------------------------------------- |
| **Primary use case**        | Metrics, dashboards, system monitoring  | Log analysis, search, and visualization       |
| **Best with**               | Prometheus, InfluxDB, Loki, Graphite    | Elasticsearch                                 |
| **Log support**             | Yes (via Loki, Elasticsearch, etc.)     | Excellent (native in ELK stack)               |
| **Metrics support**         | Excellent                               | Limited                                       |
| **Alerting**                | Built-in, powerful                      | Built-in, basic unless using Elastic features |
| **Data source flexibility** | Wide variety (many plugins)             | Mainly Elasticsearch                          |
| **UI/UX**                   | Clean, modern, focused on metrics       | Rich, tailored to logs and search             |
| **Setup Complexity**        | Simple with Prometheus stack            | More complex (needs Elasticsearch)            |
| **Open Source**             | Yes (core), Enterprise add-ons optional | Yes (basic), but some features are paid       |
