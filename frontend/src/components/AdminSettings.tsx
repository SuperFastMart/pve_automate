import { useState, useEffect } from 'react'
import { useSettings, useBulkUpdateSettings, useDeleteSetting, useTestProxmox, useTestJira, useTestPhpIpam } from '../hooks/useSettings'
import type { SettingsGroup } from '../types'

function SettingsGroupCard({ group, onSaved }: { group: SettingsGroup; onSaved: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [dirty, setDirty] = useState(false)

  const bulkUpdate = useBulkUpdateSettings()
  const deleteSetting = useDeleteSetting()
  const testProxmox = useTestProxmox()
  const testJira = useTestJira()
  const testPhpIpam = useTestPhpIpam()

  useEffect(() => {
    const initial: Record<string, string> = {}
    group.settings.forEach((s) => {
      // For secrets from DB, show the masked value; user can clear and type new
      initial[s.key] = s.is_secret && s.source === 'database' ? '' : s.value
    })
    setValues(initial)
    setDirty(false)
  }, [group])

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  const handleSave = () => {
    // Only send non-empty values (empty means "keep existing" for secrets)
    const toSend: Record<string, string> = {}
    group.settings.forEach((s) => {
      const newVal = values[s.key]
      if (s.is_secret && s.source === 'database' && newVal === '') {
        // Secret already in DB, user didn't change it - skip
        return
      }
      if (newVal !== undefined) {
        toSend[s.key] = newVal
      }
    })

    bulkUpdate.mutate(
      { group: group.group, settings: toSend },
      {
        onSuccess: () => {
          setDirty(false)
          onSaved()
        },
      }
    )
  }

  const handleRevert = (key: string) => {
    deleteSetting.mutate(key, {
      onSuccess: () => onSaved(),
    })
  }

  const isBooleanSetting = (key: string) =>
    key === 'PVE_VERIFY_SSL' || key === 'SMTP_USE_TLS'

  const isNumberSetting = (key: string) =>
    key === 'SMTP_PORT' || key === 'PHPIPAM_DEFAULT_SUBNET_ID'

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">{group.display_name}</h3>
        <div className="flex items-center gap-2">
          {(group.group === 'proxmox' || group.group === 'jira' || group.group === 'phpipam') && (
            <button
              onClick={() => {
                if (group.group === 'proxmox') testProxmox.mutate()
                else if (group.group === 'jira') testJira.mutate()
                else if (group.group === 'phpipam') testPhpIpam.mutate()
              }}
              disabled={
                group.group === 'proxmox' ? testProxmox.isPending :
                group.group === 'jira' ? testJira.isPending :
                testPhpIpam.isPending
              }
              className="px-3 py-1.5 text-sm font-medium text-indigo-600 border border-indigo-300 rounded-md hover:bg-indigo-50 disabled:opacity-50"
            >
              {(group.group === 'proxmox' ? testProxmox.isPending :
                group.group === 'jira' ? testJira.isPending :
                testPhpIpam.isPending) ? 'Testing...' : 'Test Connection'}
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={!dirty || bulkUpdate.isPending}
            className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {bulkUpdate.isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Connection test result */}
      {group.group === 'proxmox' && testProxmox.data && (
        <div
          className={`mx-6 mt-4 px-4 py-3 rounded-md text-sm ${
            testProxmox.data.success
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {testProxmox.data.message}
        </div>
      )}
      {group.group === 'jira' && testJira.data && (
        <div
          className={`mx-6 mt-4 px-4 py-3 rounded-md text-sm ${
            testJira.data.success
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {testJira.data.message}
        </div>
      )}
      {group.group === 'phpipam' && testPhpIpam.data && (
        <div
          className={`mx-6 mt-4 px-4 py-3 rounded-md text-sm ${
            testPhpIpam.data.success
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {testPhpIpam.data.message}
        </div>
      )}

      <div className="p-6 space-y-4">
        {group.settings.map((setting) => (
          <div key={setting.key} className="flex items-start gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <label className="text-sm font-medium text-gray-700">
                  {setting.display_name}
                </label>
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${
                    setting.source === 'database'
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {setting.source === 'database' ? 'DB' : 'ENV'}
                </span>
              </div>

              {isBooleanSetting(setting.key) ? (
                <button
                  type="button"
                  onClick={() =>
                    handleChange(
                      setting.key,
                      values[setting.key] === 'true' || values[setting.key] === 'True'
                        ? 'false'
                        : 'true'
                    )
                  }
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    values[setting.key] === 'true' || values[setting.key] === 'True' || setting.value === 'True' && !values[setting.key]
                      ? 'bg-indigo-600'
                      : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      values[setting.key] === 'true' || values[setting.key] === 'True' || setting.value === 'True' && !values[setting.key]
                        ? 'translate-x-6'
                        : 'translate-x-1'
                    }`}
                  />
                </button>
              ) : (
                <input
                  type={setting.is_secret && !showSecrets[setting.key] ? 'password' : isNumberSetting(setting.key) ? 'number' : 'text'}
                  value={values[setting.key] ?? ''}
                  onChange={(e) => handleChange(setting.key, e.target.value)}
                  placeholder={setting.is_secret && setting.source === 'database' ? setting.value : ''}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              )}

              <p className="mt-0.5 text-xs text-gray-400 font-mono">{setting.key}</p>
            </div>

            <div className="flex items-center gap-1 pt-6">
              {setting.is_secret && !isBooleanSetting(setting.key) && (
                <button
                  type="button"
                  onClick={() =>
                    setShowSecrets((prev) => ({ ...prev, [setting.key]: !prev[setting.key] }))
                  }
                  className="p-1 text-gray-400 hover:text-gray-600"
                  title={showSecrets[setting.key] ? 'Hide' : 'Show'}
                >
                  {showSecrets[setting.key] ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              )}

              {setting.source === 'database' && (
                <button
                  type="button"
                  onClick={() => handleRevert(setting.key)}
                  className="p-1 text-gray-400 hover:text-red-500"
                  title="Revert to .env default"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function AdminSettings() {
  const { data: groups, isLoading, error, refetch } = useSettings()

  if (isLoading) return <p className="text-gray-500">Loading settings...</p>
  if (error) return <p className="text-red-600">Failed to load settings.</p>

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-gray-500">
          Configure integration credentials. Values stored in the database override .env defaults.
        </p>
      </div>

      {groups?.map((group) => (
        <SettingsGroupCard key={group.group} group={group} onSaved={() => refetch()} />
      ))}
    </div>
  )
}
