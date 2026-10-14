/* SPDX-License-Identifier: GPL-3.0-only */
#include "project_save_app.h"
#include "project_save_service.h"
int native_project_save_poll(lunar_project_save_service *s, fm1_app_t *app) {
    return lunar_project_save_service_poll(s, app);
}
int native_project_save_ready(const lunar_project_save_service *s) {
    return lunar_project_save_service_ready(s);
}
int native_project_save_target(fm1_app_t *app, const lunar_project_io *io,
                               uint32_t slots, fm1_state_report_t *report) {
    return lunar_project_save_app(app, io, slots, 1, 1, 1, 1, report);
}
