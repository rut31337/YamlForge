# YamlForge Role

This role provides automated installation and setup for YamlForge infrastructure generation.

## Requirements

- Python 3.8+
- pip3
- terraform >= 1.12.0 (for OpenShift/ROSA support)

## Role Variables

See `defaults/main.yml` for available variables.

## Dependencies

- yamlforge-infra pip package

## Example Playbook

```yaml
- hosts: localhost
  roles:
    - rut31337.yamlforge.yamlforge
```

## License

Apache 2.0

## Author Information

Patrick T. Rutledge III