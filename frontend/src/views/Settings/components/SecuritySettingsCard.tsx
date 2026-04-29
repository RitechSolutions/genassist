import { useEffect, useState } from "react";
import { ShieldCheck, Save } from "lucide-react";
import { Card } from "@/components/card";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { Label } from "@/components/label";
import toast from "react-hot-toast";
import { type SecuritySettings, updateSecuritySettings } from "@/services/appSettings";

const RESIDENCY_OPTIONS = [
  { value: "EU", label: "European Union (EU)" },
  { value: "CA", label: "Canada (CA)" },
  { value: "US", label: "United States (US)" },
  { value: "US_GOV", label: "US GovCloud (US_GOV)" },
  { value: "AP", label: "Asia Pacific (AP)" },
  { value: "SA", label: "South America (SA)" },
  { value: "ME", label: "Middle East (ME)" },
  { value: "AF", label: "Africa (AF)" },
  { value: "IL", label: "Israel (IL)" },
  { value: "MX", label: "Mexico (MX)" },
];

interface SecuritySettingsCardProps {
  settings: SecuritySettings | null;
  onSaved?: (updated: SecuritySettings) => void;
}

export const SecuritySettingsCard = ({ settings, onSaved }: SecuritySettingsCardProps) => {
  const toZones = (value: string[] | string | undefined): string[] =>
    Array.isArray(value) ? value : value ? [value] : [];

  const [selectedZones, setSelectedZones] = useState<string[]>(() =>
    toZones(settings?.values?.data_residency)
  );

  useEffect(() => {
    setSelectedZones(toZones(settings?.values?.data_residency));
  }, [settings]);
  const [isSaving, setIsSaving] = useState(false);

  const toggle = (zone: string) => {
    setSelectedZones((prev) =>
      prev.includes(zone) ? prev.filter((z) => z !== zone) : [...prev, zone]
    );
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      const updated: SecuritySettings = {
        ...(settings ?? { name: "Security", type: "Security", is_active: 1 }),
        values: { data_residency: selectedZones },
      };
      await updateSecuritySettings(updated);
      onSaved?.(updated);
      toast.success("Security settings saved");
    } catch {
      toast.error("Failed to save security settings");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="p-4 sm:p-6 shadow-sm animate-fade-up bg-white">
      <div className="flex items-center gap-3 mb-4">
        <ShieldCheck className="w-5 h-5 sm:w-6 sm:h-6 text-primary" />
        <div>
          <h2 className="text-base sm:text-lg font-semibold">Security Settings</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Data residency and LLM provider access policy
          </p>
        </div>
        <Button
          variant="outline"
          type="button"
          className="ml-auto rounded-full"
          loading={isSaving}
          icon={<Save className="w-4 h-4" />}
          onClick={handleSave}
        >
          Save
        </Button>
      </div>

      <div className="space-y-3">
        <div>
          <Label className="text-sm font-medium">Data Residency Zones</Label>
          <p className="text-xs text-muted-foreground mt-0.5 mb-3">
            Bedrock providers whose region falls outside all selected zones will be blocked.
            Leave all unchecked for no restriction.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {RESIDENCY_OPTIONS.map((opt) => (
              <div key={opt.value} className="flex items-center gap-2">
                <Checkbox
                  id={`zone-${opt.value}`}
                  checked={selectedZones.includes(opt.value)}
                  onCheckedChange={() => toggle(opt.value)}
                />
                <label
                  htmlFor={`zone-${opt.value}`}
                  className="text-sm cursor-pointer select-none"
                >
                  {opt.label}
                </label>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
};