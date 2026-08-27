import { Card } from '@/components/card';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/tabs';
import { SettingSection } from '../components/SettingSection';
import { useSettings } from '../hooks/useSettings';
import { settingSections } from '../helpers/settingsData';
import { getAuthMe, hasPermission } from '@/services/auth';
import { getFileManagerSettings, type FileManagerSettings } from '@/services/fileManager';
import { getSecuritySettings, type SecuritySettings } from '@/services/appSettings';
import { FileManagerSettingsCard } from '../components/FileManagerSettingsCard';
import { SecuritySettingsCard } from '../components/SecuritySettingsCard';
import { FeatureFlagsPanel } from '../panels/FeatureFlagsPanel';
import { TranslationsPanel } from '../panels/TranslationsPanel';
import { LanguagesPanel } from '../panels/LanguagesPanel';
import { NotificationsPanel } from '../panels/NotificationsPanel';
import { MaintenancePanel } from '../panels/MaintenancePanel';
import { ThemeToggle } from '@/components/ThemeToggle';
import type { User } from '@/interfaces/user.interface';

type TabKey =
  | 'profile'
  | 'notifications'
  | 'feature-flags'
  | 'translations'
  | 'languages'
  | 'file-manager'
  | 'security'
  | 'maintenance';

const SettingsPage = () => {
  const { toggleStates, handleToggle } = useSettings();
  const [userProfile, setUserProfile] = useState<User | null>(null);
  const [fileManagerSettings, setFileManagerSettings] = useState<FileManagerSettings | null>(null);
  const [securitySettings, setSecuritySettings] = useState<SecuritySettings | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const me = await getAuthMe();
        setUserProfile(me);
      } catch {
        setUserProfile(null);
      }
    };
    const fetchFileManagerSettings = async () => {
      const settings = await getFileManagerSettings();
      setFileManagerSettings(settings);
    };
    const fetchSecuritySettings = async () => {
      const settings = await getSecuritySettings();
      setSecuritySettings(settings);
    };
    fetchProfile();
    if (hasPermission('write:app_settings')) {
      fetchFileManagerSettings();
      fetchSecuritySettings();
    }
  }, []);

  const profileSection = useMemo(() => {
    const tenant = localStorage.getItem('tenant_id') || '-';
    const profileValues = {
      fullName: userProfile?.username || userProfile?.email || '',
      username: userProfile?.username || '',
      email: userProfile?.email || '',
      roles: userProfile?.roles?.map((r) => r.name).filter(Boolean) ?? [],
      tenant,
    };

    const base = settingSections.find((section) => section.title === 'Profile Settings');
    if (!base) return null;
    return {
      ...base,
      fields: base.fields.map((field) => ({
        ...field,
        readOnly: true,
        className: 'w-1/2',
        value: field.valueKey
          ? (profileValues[field.valueKey as keyof typeof profileValues] ?? (field.type === 'tags' ? [] : ''))
          : field.type === 'tags'
            ? []
            : '',
      })),
    };
  }, [userProfile]);

  const fileManagerEnabled =
    fileManagerSettings?.values.file_manager_enabled === true &&
    fileManagerSettings.is_active === 1;

  // Tabs available to this user, honoring the same permissions as the routes.
  const tabs = useMemo(
    () =>
      (
        [
          { key: 'profile', label: 'Profile', show: true },
          { key: 'notifications', label: 'Notifications', show: true },
          { key: 'feature-flags', label: 'Feature Flags', show: hasPermission('read:feature_flag') },
          { key: 'translations', label: 'Translations', show: hasPermission('read:app_setting') },
          { key: 'languages', label: 'Languages', show: hasPermission('read:app_setting') },
          { key: 'file-manager', label: 'File Manager', show: hasPermission('write:app_settings') },
          { key: 'security', label: 'Security', show: hasPermission('write:app_settings') },
          { key: 'maintenance', label: 'Maintenance', show: hasPermission('write:app_settings') },
        ] as { key: TabKey; label: string; show: boolean }[]
      ).filter((t) => t.show),
    []
  );

  const validKeys = tabs.map((t) => t.key);
  const requestedTab = searchParams.get('tab') as TabKey | null;
  const activeTab: TabKey =
    requestedTab && validKeys.includes(requestedTab) ? requestedTab : 'profile';

  const handleTabChange = (value: string) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', value);
        return next;
      },
      { replace: true }
    );
  };

  return (
    <>
      <div className="flex-1 p-4 sm:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          <header className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold mb-2 animate-fade-down">Settings</h1>
              <p className="text-sm sm:text-base text-muted-foreground animate-fade-up">
                Manage your account settings and preferences
              </p>
            </div>
            <ThemeToggle className="shrink-0 animate-fade-down" />
          </header>

          <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
            <div className="-mx-1 mb-6 overflow-x-auto px-1 pb-1">
              <TabsList className="w-max">
                {tabs.map((t) => (
                  <TabsTrigger key={t.key} value={t.key}>
                    {t.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>

            <TabsContent value="profile" className="mt-0">
              {profileSection && (
                <SettingSection
                  section={profileSection}
                  toggleStates={toggleStates}
                  onToggle={handleToggle}
                />
              )}
            </TabsContent>

            <TabsContent value="notifications" className="mt-0">
              <NotificationsPanel variant="tab" />
            </TabsContent>

            {hasPermission('read:feature_flag') && (
              <TabsContent value="feature-flags" className="mt-0">
                <FeatureFlagsPanel variant="tab" />
              </TabsContent>
            )}

            {hasPermission('read:app_setting') && (
              <TabsContent value="translations" className="mt-0">
                <TranslationsPanel variant="tab" />
              </TabsContent>
            )}

            {hasPermission('read:app_setting') && (
              <TabsContent value="languages" className="mt-0">
                <LanguagesPanel variant="tab" />
              </TabsContent>
            )}

            {hasPermission('write:app_settings') && (
              <TabsContent value="file-manager" className="mt-0">
                {fileManagerEnabled && fileManagerSettings ? (
                  <FileManagerSettingsCard settings={fileManagerSettings} />
                ) : (
                  <Card className="p-6 shadow-sm animate-fade-up bg-card dark:bg-zinc-900">
                    <h2 className="text-base sm:text-lg font-semibold mb-2">File Manager Settings</h2>
                    <p className="text-sm text-muted-foreground">
                      File manager is not enabled or is disabled in the database. Please contact your
                      administrator to enable it.
                    </p>
                  </Card>
                )}
              </TabsContent>
            )}

            {hasPermission('write:app_settings') && (
              <TabsContent value="security" className="mt-0">
                <SecuritySettingsCard
                  settings={securitySettings}
                  onSaved={(updated) => setSecuritySettings(updated)}
                />
              </TabsContent>
            )}

            {hasPermission('write:app_settings') && (
              <TabsContent value="maintenance" className="mt-0">
                <MaintenancePanel variant="tab" />
              </TabsContent>
            )}
          </Tabs>
        </div>
      </div>
      <footer className="mt-4">
        <div className="max-w-7xl mx-auto w-full">
          <p className="text-right px-2 sm:px-4 text-xs sm:text-sm text-muted-foreground">
            Version: <span>{import.meta.env.VITE_UI_VERSION || '1.0'}</span>
          </p>
        </div>
      </footer>
    </>
  );
};

export default SettingsPage;
