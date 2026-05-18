"use client";

// Compatibility shim — the original single-step dialog was replaced by the
// five-step New Project Wizard (see ./create-project-wizard.tsx). Keep the
// CreateProjectDialog export so existing call sites (notably
// app/projects/page.tsx) don't need to change imports.
export { CreateProjectWizard as CreateProjectDialog } from "./create-project-wizard";
