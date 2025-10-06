import { useAuth } from '@/hooks/useAuth';
import { MessageSquare, FileText, Clock } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { FeatureCard } from '@/components/ui/grid-feature-cards';

export default function Dashboard() {
  const { user } = useAuth();

  const stats = [
    {
      title: 'My Enquiries',
      icon: MessageSquare,
      description: 'Track all your product enquiries and conversations in one place.',
      count: 0,
    },
    {
      title: 'My Quotes',
      icon: FileText,
      description: 'View and manage all your received quotes and proposals.',
      count: 0,
    },
    {
      title: 'Pending Review',
      icon: Clock,
      description: 'Quotes awaiting review and approval from our team.',
      count: 0,
    },
  ];

  return (
    <div className="min-h-screen p-4 md:p-8">
      <AnimatedContainer className="max-w-5xl mx-auto space-y-8">
        <div className="text-left">
          <h1 className="text-3xl md:text-4xl font-bold tracking-wide">
            Welcome back, {user?.full_name || user?.email?.split('@')[0]}!
          </h1>
          <p className="text-muted-foreground mt-2 text-sm md:text-base">
            Here's an overview of your account activity
          </p>
        </div>

        <AnimatedContainer
          delay={0.2}
          className="grid grid-cols-1 divide-x divide-y divide-dashed border border-dashed rounded-lg overflow-hidden sm:grid-cols-2 md:grid-cols-3 bg-white"
        >
          {stats.map((stat, i) => (
            <div key={i} className="relative">
              <FeatureCard feature={stat} />
              <div className="absolute top-6 right-6">
                <span className="text-2xl md:text-3xl font-bold text-foreground/20">
                  {stat.count}
                </span>
              </div>
            </div>
          ))}
        </AnimatedContainer>

        {/* Recent Activity Section */}
        <AnimatedContainer delay={0.4} className="space-y-4">
          <h2 className="text-xl md:text-2xl font-semibold">Recent Activity</h2>
          <div className="border border-dashed rounded-lg p-8 text-center bg-white">
            <p className="text-muted-foreground text-sm">
              No recent activity yet. Start by creating an enquiry!
            </p>
          </div>
        </AnimatedContainer>
      </AnimatedContainer>
    </div>
  );
}

function AnimatedContainer({ className, delay = 0.1, children }) {
  const shouldReduceMotion = useReducedMotion();

  if (shouldReduceMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      initial={{ filter: 'blur(4px)', translateY: -8, opacity: 0 }}
      whileInView={{ filter: 'blur(0px)', translateY: 0, opacity: 1 }}
      viewport={{ once: true }}
      transition={{ delay, duration: 0.8 }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
