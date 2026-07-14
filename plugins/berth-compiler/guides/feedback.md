# Post-publish platform and Plugin feedback

Generate `问题梳理与优化意见清单.md` after successful deployment.

Use this structure:

```markdown
# Berth 平台与 Compiler Plugin 问题梳理与优化建议

## 复盘范围
- Plugin / version
- Platform / contract version
- Operation: create or reconstruct
- Agent Package(s)
- Publish Job(s) and result

## P0：阻断创建、转换、验证或发布
### Finding
**Evidence**
**Root cause**
**Recommended platform/Plugin change**

## P1：显著降低效率、稳定性或还原度
...

## P2：引导、语义、访谈和体验问题
...

## 本次已自动绕过或修复
...

## 未发现问题的检查项
...
```

Exclude ordinary domain defects in the generated Agent. Include a finding only when the platform or Plugin could prevent, detect, explain, automate, or guide the issue better. Never include tokens, provider keys, private user content, or secrets.
