import React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Switch } from "@/components/switch";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/form";
import { FeatureFlagFormData } from "@/interfaces/featureFlag.interface";

const formSchema = z.object({
  key: z.string().min(1, "Key is required"),
  val: z.string().min(1, "Value is required"),
  description: z.string().optional(),
  is_active: z.boolean().default(true),
});
type FeatureFlagFormFields = z.infer<typeof formSchema>;

interface FeatureFlagFormProps {
  initialData?: FeatureFlagFormData;
  onSubmit: (data: FeatureFlagFormData) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function FeatureFlagForm({
  initialData,
  onSubmit,
  onCancel,
  isSubmitting,
}: FeatureFlagFormProps) {
  const form = useForm<FeatureFlagFormFields>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      key: initialData?.key || "",
      val: initialData?.val || "",
      description: initialData?.description || "",
      is_active: initialData ? initialData.is_active === 1 : true,
    },
  });

  const handleSubmit = (values: FeatureFlagFormFields) => {
    const data: FeatureFlagFormData = {
      key: values.key,
      val: values.val,
      description: values.description || "",
      is_active: values.is_active ? 1 : 0,
    };
    
    if (initialData?.id) {
      data.id = initialData.id;
    }
    
    onSubmit(data);
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="key"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Key</FormLabel>
              <FormControl>
                <Input 
                  placeholder="feature.name" 
                  {...field} 
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="val"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Value</FormLabel>
              <FormControl>
                <Input placeholder="true, false, or a variant value" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Description of what this feature flag controls"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="is_active"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <FormLabel className="text-base">Active</FormLabel>
                <FormDescription>
                  Whether this feature flag is currently active
                </FormDescription>
              </div>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
          )}
        />

        <div className="flex items-center justify-end space-x-4">
          <Button variant="outline" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {initialData?.id ? "Update" : "Create"} Feature Flag
          </Button>
        </div>
      </form>
    </Form>
  );
} 