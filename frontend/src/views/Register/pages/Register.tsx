import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { RegisterForm } from "../components/RegisterForm";
import TermsAndPolicyNotice from "@/components/TermsAndPolicyNotice";
import { AuthMockupPanel } from "@/components/AuthMockupPanel";
import { GenAssistLogo } from "@/components/GenAssistLogo";

const RegisterPage = () => {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleRegister = async (
    username: string,
    password: string,
    confirmPassword: string
  ) => {
    if (password !== confirmPassword) {
      toast.error("Passwords do not match.");
      return;
    }

    setIsLoading(true);

    try {
      // Add your registration logic here
      // For now, just simulate success
      toast.success("Account created successfully.");
      navigate("/login");
    } catch (error) {
      toast.error("Failed to create account.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2">
      <div className="flex items-center justify-center p-4 bg-white">
        <div className="w-full max-w-md space-y-6">
          <div className="space-y-2">
            <GenAssistLogo width={200} height={52} />

            <h1 className="text-3xl font-bold tracking-tight">
              Create an account
            </h1>
            <p className="text-zinc-500">
              Enter your details to create your account
            </p>
          </div>

          <RegisterForm onSubmit={handleRegister} isLoading={isLoading} />

          <div className="text-center text-sm mt-8">
            <span className="text-zinc-500">Already have an account? </span>
            <Link
              to="/login"
              className="text-black hover:underline font-medium"
            >
              Sign in
            </Link>
          </div>

          <TermsAndPolicyNotice mode="signup" className="mt-2" />
        </div>
      </div>
      <AuthMockupPanel />
    </div>
  );
};

export default RegisterPage;
