# Release Notes — {{buildDetails.buildNumber}}

**Date:** {{buildDetails.startTime}}  
**Branch:** {{buildDetails.sourceBranch}}  
**Commit:** {{buildDetails.sourceVersion}}

---

{{#with (buildGroups pullRequests) as |groups|}}

## 🔥 Urgent
{{#if groups.urgent.length}}
{{#forEach groups.urgent}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## 🐛 Bug Fixes
{{#if groups.bugFixes.length}}
{{#forEach groups.bugFixes}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## ✨ Enhancements
{{#if groups.enhancements.length}}
{{#forEach groups.enhancements}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## 📚 Documentation
{{#if groups.documentation.length}}
{{#forEach groups.documentation}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## 🧩 Plugin
{{#if groups.plugin.length}}
{{#forEach groups.plugin}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## 🖥️ Frontend
{{#if groups.frontend.length}}
{{#forEach groups.frontend}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## 🧠 Backend
{{#if groups.backend.length}}
{{#forEach groups.backend}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## 🧾 Other
{{#if groups.other.length}}
{{#forEach groups.other}}
- PR #{{pullRequestId}} — **{{title}}**
  - Link: {{url}}
  - Author: {{createdBy.displayName}}
  - Labels: {{labelsCsv}}
{{/forEach}}
{{else}}
_None_
{{/if}}

---

## ✅ All merged PRs in this release
{{#if groups.all.length}}
{{#forEach groups.all}}
- PR #{{pullRequestId}} — **{{title}}** ({{url}})
{{/forEach}}
{{else}}
_None_
{{/if}}

{{/with}}
