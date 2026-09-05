export type StatusTone = 'pass' | 'warning' | 'violation' | 'review' | 'neutral'

export const overviewStats = [
  { label: 'Inspections this month', value: '184', change: '+12.4%', tone: 'pass' as const },
  { label: 'Manual review queue', value: '27', change: '-8.1%', tone: 'review' as const },
  { label: 'High-risk findings', value: '13', change: '+3.2%', tone: 'violation' as const },
  { label: 'Average compliance score', value: '92.6%', change: '+2.3%', tone: 'pass' as const },
]

export const complianceTrend = [
  { month: 'Jan', pass: 76, warning: 18, violation: 6 },
  { month: 'Feb', pass: 81, warning: 14, violation: 5 },
  { month: 'Mar', pass: 84, warning: 12, violation: 4 },
  { month: 'Apr', pass: 88, warning: 9, violation: 3 },
  { month: 'May', pass: 91, warning: 7, violation: 2 },
  { month: 'Jun', pass: 94, warning: 5, violation: 1 },
]

export const violationBreakdown = [
  { name: 'Packaging', value: 42, fill: '#1f6feb' },
  { name: 'Labeling', value: 26, fill: '#f59e0b' },
  { name: 'Weight', value: 18, fill: '#ef4444' },
  { name: 'Safety', value: 14, fill: '#10b981' },
]

export const recentInspections = [
  { id: 'INSP-24091', product: 'Cement Bag 50kg', inspector: 'A. Nair', status: 'pass' as const, date: '2026-09-01', score: '96%' },
  { id: 'INSP-24088', product: 'Detergent Pack 2L', inspector: 'R. Verma', status: 'warning' as const, date: '2026-09-01', score: '82%' },
  { id: 'INSP-24077', product: 'Edible Oil 1L', inspector: 'S. Kumar', status: 'review' as const, date: '2026-08-31', score: '74%' },
  { id: 'INSP-24069', product: 'Rice Packet 5kg', inspector: 'M. Sen', status: 'violation' as const, date: '2026-08-30', score: '61%' },
]

export const attentionFindings = [
  { title: 'Net content mismatch on front panel', product: 'Rice Packet 5kg', rule: 'Rule 4.2 - Quantity declaration', severity: 'High', status: 'violation' as const },
  { title: 'Mandatory warning mark partially obscured', product: 'Detergent Pack 2L', rule: 'Rule 7.1 - Warning legend', severity: 'Medium', status: 'warning' as const },
  { title: 'Expiry date field missing vendor code', product: 'Edible Oil 1L', rule: 'Rule 2.3 - Date integrity', severity: 'Medium', status: 'review' as const },
]

export const productRows = [
  { category: 'Packaged Foods', product: 'Rice Packet 5kg', compliance: 61, status: 'violation' as const },
  { category: 'Household', product: 'Detergent Pack 2L', compliance: 82, status: 'warning' as const },
  { category: 'Edible Oils', product: 'Mustard Oil 1L', compliance: 88, status: 'pass' as const },
  { category: 'Chemicals', product: 'Industrial Cleaner 500ml', compliance: 76, status: 'warning' as const },
]

export const violationRows = [
  { id: 'V-1041', rule: 'R-04.2', product: 'Rice Packet 5kg', status: 'violation' as const, owner: 'Inspector A. Nair', date: '2026-09-01' },
  { id: 'V-1042', rule: 'R-07.1', product: 'Detergent Pack 2L', status: 'warning' as const, owner: 'Inspector R. Verma', date: '2026-09-01' },
  { id: 'V-1043', rule: 'R-02.3', product: 'Edible Oil 1L', status: 'review' as const, owner: 'Inspector S. Kumar', date: '2026-08-31' },
  { id: 'V-1044', rule: 'R-05.9', product: 'Cement Bag 50kg', status: 'pass' as const, owner: 'Inspector M. Sen', date: '2026-08-30' },
]

export const reportRows = [
  { id: 'RPT-2101', product: 'Rice Packet 5kg', inspector: 'A. Nair', status: 'violation' as const, generated: '2026-09-01 15:40' },
  { id: 'RPT-2098', product: 'Detergent Pack 2L', inspector: 'R. Verma', status: 'warning' as const, generated: '2026-09-01 11:05' },
  { id: 'RPT-2093', product: 'Cement Bag 50kg', inspector: 'M. Sen', status: 'pass' as const, generated: '2026-08-30 09:12' },
]

export const ruleRows = [
  { code: 'R-02.3', name: 'Date integrity and format', category: 'Labelling', severity: 'Medium' },
  { code: 'R-04.2', name: 'Quantity declaration validation', category: 'Measurement', severity: 'High' },
  { code: 'R-05.9', name: 'Safety warning placement', category: 'Safety', severity: 'High' },
  { code: 'R-07.1', name: 'Mandatory legends visibility', category: 'Packaging', severity: 'Medium' },
]

export const userRows = [
  { name: 'Asha Nair', role: 'Inspector', team: 'North Zone', status: 'active' as const },
  { name: 'Rohit Verma', role: 'Senior Inspector', team: 'Central Zone', status: 'active' as const },
  { name: 'Suman Kumar', role: 'Reviewer', team: 'Quality Audit', status: 'review' as const },
  { name: 'Megha Sen', role: 'Administrator', team: 'Operations', status: 'active' as const },
]

export const settingsGroups = [
  { name: 'Inspection defaults', description: 'Default workflow and evidence capture options' },
  { name: 'Evidence retention', description: 'Retention policy and audit logging preferences' },
  { name: 'Compliance thresholds', description: 'Current rule weightings and escalation thresholds' },
]
