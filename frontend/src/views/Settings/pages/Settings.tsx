import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { Card } from "@/components/card";
import { Button } from "@/components/button";
import { useIsMobile } from "@/hooks/useMobile";
import { useEffect, useMemo, useState } from "react";
import { SettingSection } from "../components/SettingSection";
import { useSettings } from "../hooks/useSettings";
import { settingSections } from "../helpers/settingsData";
import { Link } from "react-router-dom";
import { getAuthMe } from "@/services/auth";
import type { User } from "@/interfaces/user.interface";

const SettingsPage = () => {
  const { toggleStates, handleToggle, saveSettings } = useSettings();
  const [isSaving, setIsSaving] = useState(false);
  const [userProfile, setUserProfile] = useState<User | null>(null);
  const isMobile = useIsMobile();

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const me = await getAuthMe();
        setUserProfile(me);
      } catch {
        setUserProfile(null);
      }
    };
    fetchProfile();
  }, []);

  const sectionsWithData = useMemo(() => {
    const tenant = localStorage.getItem("tenant_id") || "-";
    const profileValues = {
      fullName: userProfile?.username || userProfile?.email || "",
      username: userProfile?.username || "",
      email: userProfile?.email || "",
      tenant,
    };

    return settingSections.map((section) =>
      section.title === "Profile Settings"
        ? {
            ...section,
            fields: section.fields.map((field) => ({
              ...field,
              readOnly: true,
              className: "w-1/2",
              value:
                (field.valueKey &&
                  profileValues[
                    field.valueKey as keyof typeof profileValues
                  ]) ||
                "",
            })),
          }
        : section
    );
  }, [userProfile]);

  const handleSave = async () => {
    setIsSaving(true);
    await saveSettings();
    setIsSaving(false);
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 relative">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-8">
            <div className="max-w-7xl mx-auto">
              <header className="mb-8">
                <h1 className="text-2xl sm:text-3xl font-bold mb-2 animate-fade-down">Settings</h1>
                <p className="text-sm sm:text-base text-muted-foreground animate-fade-up">
                  Manage your account settings and preferences
                </p>
              </header>

              <div className="grid grid-cols-1">
                {sectionsWithData.map((section) => (
                  <SettingSection 
                    key={section.title} 
                    section={section} 
                    toggleStates={toggleStates}
                    onToggle={handleToggle} 
                  />
                ))}

                <Card className="md:col-span-2 mt-6">
                  <div className="p-6">
                    <h2 className="text-xl font-semibold mb-4 animate-fade-up">Advanced Configuration</h2>
                    <div className="space-y-4">
                      <div className="flex flex-col">
                        <h3 className="font-medium animate-fade-up animate-delay-100">Feature Flags</h3>
                        <p className="text-sm text-muted-foreground mb-2 animate-fade-up animate-delay-200">
                          Configure feature flags to control application functionality
                        </p>
                        <Link to="/settings/feature-flags">
                          <Button variant="outline" className="mt-2 animate-fade-up animate-delay-300">
                            Manage Feature Flags
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </div>
                </Card>

                {/* <div className="md:col-span-2 flex justify-end gap-4 pt-4">
                  <Button variant="outline">Cancel</Button>
                  <Button onClick={handleSave} disabled={isSaving}>
                    {isSaving ? "Saving..." : "Save Changes"}
                  </Button>
                </div> */}
              </div>
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default SettingsPage; 