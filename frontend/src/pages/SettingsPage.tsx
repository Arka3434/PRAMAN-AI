import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { PageHeader } from '../components/ui/page-header'
import { settingsGroups } from '../data/mockData'

export function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" description="Configuration for inspection defaults, evidence handling, and operational thresholds." action={<Button>Save changes</Button>} />

      <div className="grid gap-6 lg:grid-cols-3">
        {settingsGroups.map((group) => (
          <Card key={group.name}>
            <CardHeader>
              <CardTitle>{group.name}</CardTitle>
              <CardDescription>{group.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                Configuration ready for the next implementation milestone.
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
