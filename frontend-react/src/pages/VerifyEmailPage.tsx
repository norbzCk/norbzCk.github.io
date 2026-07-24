import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext';
import { PageSection } from '../components/ui/PageSections';

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { verifyEmail } = useAuth();
  const [message, setMessage] = useState('Verifying your email...');
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    const token = searchParams.get('token');

    if (token) {
      verifyEmail(token)
        .then(() => {
          setMessage('Email verified successfully! You can now log in.');
          setIsSuccess(true);
          setTimeout(() => {
            navigate('/login');
          }, 3000);
        })
        .catch((error) => {
          setMessage(error.message || 'Email verification failed.');
          setIsSuccess(false);
        });
    } else {
      setMessage('No verification token found.');
      setIsSuccess(false);
    }
  }, [searchParams, navigate, verifyEmail]);

  return (
    <PageSection title={isSuccess ? 'Verification Successful' : 'Verification Failed'}>
      <p>{message}</p>
      {isSuccess && <p>Redirecting to login...</p>}
    </PageSection>
  );
}
